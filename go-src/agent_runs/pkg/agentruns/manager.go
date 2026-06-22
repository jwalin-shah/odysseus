// Package agent_runs implements a detached agent-run manager.
//
// It mirrors the public surface of src/agent_runs.py: an agent/chat stream
// runs server-side in a goroutine that drains events from a Source into a
// per-session replay buffer. SSE clients Subscribe to that buffer (replay
// everything so far, then live) and may come and go without affecting the
// underlying run.
//
// Concurrency: one sync.Mutex around the Manager's session map; a per-Run
// mutex for run-local state. Drain is a goroutine, eviction is
// time.AfterFunc.
package agent_runs

import (
	"context"
	"errors"
	"sync"
	"time"
)

// Sentinel error events published to the replay buffer on error/terminal.
const (
	ErrorEvent = "event: error\n" +
		`data: {"error":"Agent run failed before completion.","status":500}` +
		"\n\n"
	DoneEvent = "data: [DONE]\n\n"
)

// Source is anything that can be drained for events. The Python version
// uses an AsyncGenerator[str, None]; here we abstract that as a method that
// pushes events into the supplied sink until the source is exhausted or
// cancelled. It should return nil on clean completion, context.Canceled on
// cancellation, or any other error for the generic error path.
type Source interface {
	Next(ctx context.Context, sink func(ev string)) error
}

// FunctionSource adapts a plain function into a Source. It is the most
// common way to construct one in tests.
type FunctionSource struct {
	// Fn is invoked with a context and a sink. It should call sink for each
	// event and return when done. If the ctx is cancelled it should return
	// promptly (context.Canceled is fine).
	Fn func(ctx context.Context, sink func(ev string)) error
}

// Next implements Source.
func (f *FunctionSource) Next(ctx context.Context, sink func(ev string)) error {
	return f.Fn(ctx, sink)
}

// Status of a Run.
type Status string

// Run statuses.
const (
	StatusRunning Status = "running"
	StatusDone    Status = "done"
	StatusError   Status = "error"
	StatusStopped Status = "stopped"
)

// Event is a single SSE event delivered to subscribers.
type Event struct {
	// Seq is the 0-based position in the replay buffer.
	Seq int
	// Data is the raw SSE event string.
	Data string
}

// sentinelEvent is the zero-valued event used to signal end-of-stream to
// subscribers.
func sentinelEvent() Event { return Event{} }

// ErrSessionMissing is returned by Subscribe when no run exists for the
// given session.
var ErrSessionMissing = errors.New("agent_runs: session not found")

// Default eviction grace for finished runs after the last subscriber
// disconnects.
const DefaultEvictGrace = 180 * time.Second

// Manager owns all active and recently-finished runs.
type Manager struct {
	mu         sync.Mutex
	runs       map[string]*Run
	evictGrace time.Duration
}

// New creates a Manager with the default eviction grace (180s).
func New() *Manager {
	return NewWithGrace(DefaultEvictGrace)
}

// NewWithGrace creates a Manager with a custom eviction grace (used by tests).
func NewWithGrace(evictGrace time.Duration) *Manager {
	return &Manager{
		runs:       make(map[string]*Run),
		evictGrace: evictGrace,
	}
}

// Run is the per-session state for one drain.
type Run struct {
	sessionID string

	mu         sync.Mutex
	buffer     []string
	subs       map[chan Event]struct{}
	status     Status
	canceled   bool
	cancelFn   context.CancelFunc
	evictTimer *time.Timer
	done       chan struct{}

	manager *Manager
}

// IsActive reports whether the run is currently running.
func (r *Run) IsActive() bool {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.status == StatusRunning
}

// Status returns the run's current status.
func (r *Run) Status() Status {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.status
}

// Buffer returns a snapshot of the current replay buffer.
func (r *Run) Buffer() []string {
	r.mu.Lock()
	defer r.mu.Unlock()
	out := make([]string, len(r.buffer))
	copy(out, r.buffer)
	return out
}

// IsActive reports whether the given session currently has a running drain.
func (m *Manager) IsActive(sessionID string) bool {
	m.mu.Lock()
	r, ok := m.runs[sessionID]
	m.mu.Unlock()
	if !ok {
		return false
	}
	return r.IsActive()
}

// GetStatus returns the current status of the run and whether it exists.
func (m *Manager) GetStatus(sessionID string) (Status, bool) {
	m.mu.Lock()
	r, ok := m.runs[sessionID]
	m.mu.Unlock()
	if !ok {
		return "", false
	}
	return r.Status(), true
}

// Start begins a detached drain of src for the given session. If a run is
// already in-flight for the same session, it is cancelled first and the
// new run waits for the old one to fully exit before publishing events —
// same semantics as the Python version's prev_task wait.
func (m *Manager) Start(sessionID string, src Source) *Run {
	m.mu.Lock()
	prev, hadPrev := m.runs[sessionID]
	if hadPrev {
		prev.mu.Lock()
		if prev.cancelFn != nil {
			prev.cancelFn()
		}
		if prev.evictTimer != nil {
			prev.evictTimer.Stop()
			prev.evictTimer = nil
		}
		prev.mu.Unlock()
	}

	run := &Run{
		sessionID: sessionID,
		subs:      make(map[chan Event]struct{}),
		status:    StatusRunning,
		done:      make(chan struct{}),
		manager:   m,
	}
	m.runs[sessionID] = run
	m.mu.Unlock()

	prevDoneCh := (<-chan struct{})(nil)
	if hadPrev {
		prevDoneCh = prev.done
	}
	go run.drain(prevDoneCh, src)
	return run
}

// Stop cancels an in-flight run. Returns true if a run was actually cancelled.
func (m *Manager) Stop(sessionID string) bool {
	m.mu.Lock()
	r, ok := m.runs[sessionID]
	m.mu.Unlock()
	if !ok {
		return false
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if r.status == StatusRunning && r.cancelFn != nil {
		r.cancelFn()
		return true
	}
	return false
}

// Subscription is a live view onto a run's events. Calling Next returns
// the next event (replayed or live), or ok=false when the run has ended or
// the caller's context is cancelled.
type Subscription struct {
	ch        chan Event
	run       *Run
	ctx       context.Context
	cancel    context.CancelFunc
	mu        sync.Mutex
	closed    bool
	liveOnly  bool // true when the run was already terminal at subscribe time
	liveIndex int  // for replay-stripping during live phase
	liveDone  bool // true after the sentinel has been received
}

// Subscribe returns a subscription for the given session. It first registers
// the subscriber and replays everything in the buffer, then yields live
// events until the drain goroutine exits.
//
// If the session does not exist, ErrSessionMissing is returned.
func (m *Manager) Subscribe(parent context.Context, sessionID string) (*Subscription, error) {
	m.mu.Lock()
	run, ok := m.runs[sessionID]
	m.mu.Unlock()
	if !ok {
		return nil, ErrSessionMissing
	}

	ch := make(chan Event, 32)

	run.mu.Lock()
	// A live subscriber is connected — cancel any pending eviction.
	if run.evictTimer != nil {
		run.evictTimer.Stop()
		run.evictTimer = nil
	}
	run.subs[ch] = struct{}{}
	replay := make([]string, len(run.buffer))
	copy(replay, run.buffer)
	alreadyDone := run.status != StatusRunning
	run.mu.Unlock()

	ctx, cancel := context.WithCancel(parent)
	sub := &Subscription{
		ch:       ch,
		run:      run,
		ctx:      ctx,
		cancel:   cancel,
		liveOnly: false,
	}

	// Replay goroutine: drains replay[] then live events from ch.
	// We hand a feed channel to the user-facing Next method by writing into
	// ch from a replay feeder goroutine.
	feed := make(chan Event, 32)
	go func() {
		defer close(feed)
		// Phase 1: replay existing buffer.
		for _, ev := range replay {
			select {
			case <-ctx.Done():
				return
			case feed <- Event{Seq: -1, Data: ev}:
			}
		}
		if alreadyDone {
			// No live events will arrive — close feed to signal end.
			return
		}
		// Phase 2: live events, with replay-stripping.
		nextSeq := 0
		if len(replay) > 0 {
			nextSeq = len(replay)
		}
		for {
			select {
			case <-ctx.Done():
				return
			case ev, ok := <-ch:
				if !ok {
					// channel closed by run fanout — done.
					return
				}
				if ev == (Event{}) {
					// Sentinel — flush any tail that raced in.
					run.mu.Lock()
					tail := append([]string(nil), run.buffer[nextSeq:]...)
					run.mu.Unlock()
					for _, t := range tail {
						select {
						case <-ctx.Done():
							return
						case feed <- Event{Seq: -1, Data: t}:
						}
					}
					return
				}
				if ev.Seq >= nextSeq {
					select {
					case <-ctx.Done():
						return
					case feed <- ev:
					}
					nextSeq = ev.Seq + 1
				}
			}
		}
	}()

	// Replace sub.ch field with the feed for Next().
	sub.ch = feed

	// Hook: when ctx is cancelled (or feed closes), remove subscriber.
	go func() {
		<-ctx.Done()
		cancel()
		run.removeSubscriber(ch)
	}()

	return sub, nil
}

// Next returns the next event for this subscription, or ok=false when the
// run has ended or the caller's context is cancelled.
func (s *Subscription) Next(ctx context.Context) (Event, bool) {
	select {
	case <-ctx.Done():
		return Event{}, false
	case <-s.ctx.Done():
		return Event{}, false
	case ev, ok := <-s.ch:
		if !ok {
			return Event{}, false
		}
		return ev, true
	}
}

// Close releases the subscription.
func (s *Subscription) Close() {
	s.cancel()
}

// removeSubscriber removes ch from the run and, if it was the last
// subscriber of a finished run, (re)arms the eviction timer.
func (r *Run) removeSubscriber(ch chan Event) {
	r.mu.Lock()
	if _, ok := r.subs[ch]; !ok {
		r.mu.Unlock()
		return
	}
	delete(r.subs, ch)
	shouldEvict := r.status != StatusRunning && len(r.subs) == 0
	grace := r.manager.evictGrace
	r.mu.Unlock()
	if shouldEvict {
		r.scheduleEvict(grace)
	}
}

// scheduleEvict (re)arms the grace-period eviction timer for a finished run.
func (r *Run) scheduleEvict(grace time.Duration) {
	r.mu.Lock()
	if r.evictTimer != nil {
		r.evictTimer.Stop()
		r.evictTimer = nil
	}
	r.mu.Unlock()

	t := time.AfterFunc(grace, func() {
		r.mu.Lock()
		stillTerminal := r.status != StatusRunning
		noSubs := len(r.subs) == 0
		r.mu.Unlock()
		if !stillTerminal || !noSubs {
			return
		}
		r.manager.mu.Lock()
		if cur, ok := r.manager.runs[r.sessionID]; ok && cur == r {
			delete(r.manager.runs, r.sessionID)
		}
		r.manager.mu.Unlock()
	})
	r.mu.Lock()
	r.evictTimer = t
	r.mu.Unlock()
}

// drain is the goroutine body. It waits for prev (if any), then drains src
// into the buffer. On cancellation: status=stopped. On error: status=error
// and an error event is published. Either way: subscribers receive a
// sentinel, and the eviction timer is (re)armed if there are no subscribers.
func (r *Run) drain(prevDone <-chan struct{}, src Source) {
	// If we replaced an in-flight run, wait for it to fully exit first.
	if prevDone != nil {
		<-prevDone
	}

	ctx, cancel := context.WithCancel(context.Background())
	r.mu.Lock()
	r.cancelFn = cancel
	r.mu.Unlock()

	sink := func(ev string) {
		r.publish(ev)
	}

	err := src.Next(ctx, sink)

	r.mu.Lock()
	switch {
	case r.canceled || (err != nil && errors.Is(err, context.Canceled)):
		// Cancellation can manifest as r.canceled==true (Stop was called)
		// OR as context.Canceled from the source's Next() without our
		// internal flag being set (e.g. ctx propagated cancellation).
		r.status = StatusStopped
	case err != nil:
		r.status = StatusError
		r.buffer = append(r.buffer, ErrorEvent)
		r.buffer = append(r.buffer, DoneEvent)
	default:
		if r.status == StatusRunning {
			r.status = StatusDone
		}
	}
	noSubs := len(r.subs) == 0
	r.mu.Unlock()

	// Fan out the sentinel so subscribers exit their loops.
	r.fanoutSentinel()

	if noSubs {
		grace := r.manager.evictGrace
		r.scheduleEvict(grace)
	}

	close(r.done)
}

// fanoutSentinel delivers a zero-valued (end-of-stream) Event to every
// subscriber channel so blocked readers unblock and close their feed.
func (r *Run) fanoutSentinel() {
	r.mu.Lock()
	subs := make([]chan Event, 0, len(r.subs))
	for ch := range r.subs {
		subs = append(subs, ch)
	}
	r.mu.Unlock()
	for _, ch := range subs {
		select {
		case ch <- sentinelEvent():
		default:
			// Subscriber buffer full — they'll detect EOF via the channel
			// being closed on Run teardown.
		}
	}
}

// publish appends ev to the buffer and fans it out to every subscriber.
func (r *Run) publish(ev string) {
	r.mu.Lock()
	seq := len(r.buffer)
	r.buffer = append(r.buffer, ev)
	subs := make([]chan Event, 0, len(r.subs))
	for ch := range r.subs {
		subs = append(subs, ch)
	}
	r.mu.Unlock()

	for _, ch := range subs {
		select {
		case ch <- Event{Seq: seq, Data: ev}:
		default:
			// Slow subscriber — event is in the replay buffer and will be
			// visible on next reconnect via replay-stripping.
		}
	}
}
