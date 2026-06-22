package agent_runs

import (
	"context"
	"errors"
	"fmt"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// Test helpers -------------------------------------------------------------

// collect drains a subscription into a slice. Stops at EOF or ctx cancel.
func collect(t *testing.T, sub *Subscription, timeout time.Duration) []Event {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()
	var out []Event
	for {
		ev, ok := sub.Next(ctx)
		if !ok {
			return out
		}
		out = append(out, ev)
	}
}

// stringSource is a Source that yields a fixed list of events with optional
// delay. It honors context cancellation.
type stringSource struct {
	events []string
	delay  time.Duration
}

func (s *stringSource) Next(ctx context.Context, sink func(ev string)) error {
	for _, ev := range s.events {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(s.delay):
		}
		sink(ev)
	}
	return nil
}

// errSource always returns the given error.
type errSource struct{ err error }

func (e *errSource) Next(ctx context.Context, sink func(ev string)) error {
	return e.err
}

// blockingSource blocks until ctx is cancelled, then returns ctx.Err().
type blockingSource struct{}

func (b *blockingSource) Next(ctx context.Context, sink func(ev string)) error {
	<-ctx.Done()
	return ctx.Err()
}

// hangingSource waits forever; only useful with cancel.
type hangingSource struct{ hung chan struct{} }

func (h *hangingSource) Next(ctx context.Context, sink func(ev string)) error {
	h.hung <- struct{}{}
	<-ctx.Done()
	return ctx.Err()
}

// Tests --------------------------------------------------------------------

func TestStartSubscribeDrainReplayEvict(t *testing.T) {
	m := NewWithGrace(50 * time.Millisecond)
	events := []string{"e1\n", "e2\n", "e3\n"}
	m.Start("s1", &stringSource{events: events})

	// Subscribe immediately — we should replay the events as they stream.
	sub, err := m.Subscribe(context.Background(), "s1")
	if err != nil {
		t.Fatalf("Subscribe: %v", err)
	}
	got := collect(t, sub, 2*time.Second)

	want := []string{"e1\n", "e2\n", "e3\n"}
	if len(got) != len(want) {
		t.Fatalf("event count: got %d want %d (events=%v)", len(got), len(want), got)
	}
	for i := range want {
		if got[i].Data != want[i] {
			t.Errorf("event[%d]: got %q want %q", i, got[i].Data, want[i])
		}
	}

	if st, ok := m.GetStatus("s1"); !ok || st != StatusDone {
		t.Errorf("status after drain: got %v ok=%v want done", st, ok)
	}

	// Explicitly close — last subscriber gone on a finished run should
	// trigger eviction after grace.
	sub.Close()

	// Last subscriber gone on a finished run -> eviction after grace.
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		if _, ok := m.GetStatus("s1"); !ok {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	t.Errorf("run was not evicted after grace period")
}

func TestReconnectMidRunGetsReplay(t *testing.T) {
	m := NewWithGrace(50 * time.Millisecond)
	src := &slowSource{delay: 30 * time.Millisecond, total: 6}
	m.Start("s1", src)

	// Wait until a few events have been published.
	time.Sleep(80 * time.Millisecond)
	sub, err := m.Subscribe(context.Background(), "s1")
	if err != nil {
		t.Fatalf("Subscribe: %v", err)
	}
	got := collect(t, sub, 2*time.Second)

	// We should see all 6 events exactly once (replay + live, with stripping).
	if len(got) != 6 {
		t.Fatalf("event count: got %d want 6 (events=%v)", len(got), got)
	}
	for i, ev := range got {
		want := fmt.Sprintf("e%d\n", i)
		if ev.Data != want {
			t.Errorf("event[%d]: got %q want %q", i, ev.Data, want)
		}
	}
}

func TestDoubleSendCancellation(t *testing.T) {
	m := NewWithGrace(50 * time.Millisecond)
	hung := make(chan struct{})
	src1 := &hangingSource{hung: hung}
	m.Start("s1", src1)
	<-hung // src1 is now actively running

	// Start a second run for the same session — should cancel src1.
	src2 := &stringSource{events: []string{"only\n"}}
	m.Start("s1", src2)

	// Collect from src2.
	sub, err := m.Subscribe(context.Background(), "s1")
	if err != nil {
		t.Fatalf("Subscribe: %v", err)
	}
	got := collect(t, sub, 2*time.Second)
	if len(got) != 1 || got[0].Data != "only\n" {
		t.Fatalf("expected only src2 event, got %v", got)
	}
	if st, _ := m.GetStatus("s1"); st != StatusDone {
		t.Errorf("status: got %v want done", st)
	}
}

func TestStopMidRun(t *testing.T) {
	m := NewWithGrace(50 * time.Millisecond)
	hung := make(chan struct{})
	src := &hangingSource{hung: hung}
	m.Start("s1", src)
	<-hung

	if !m.Stop("s1") {
		t.Errorf("Stop returned false")
	}
	// After stop, status should be 'stopped'.
	deadline := time.Now().Add(1 * time.Second)
	for time.Now().Before(deadline) {
		if st, ok := m.GetStatus("s1"); ok && st == StatusStopped {
			return
		}
		time.Sleep(5 * time.Millisecond)
	}
	st, _ := m.GetStatus("s1")
	t.Errorf("status after stop: got %v want stopped", st)
}

func TestErrorPathPublishesErrorEvent(t *testing.T) {
	m := NewWithGrace(50 * time.Millisecond)
	src := &errSource{err: errors.New("boom")}
	m.Start("s1", src)

	// Subscribe and collect.
	sub, err := m.Subscribe(context.Background(), "s1")
	if err != nil {
		t.Fatalf("Subscribe: %v", err)
	}
	got := collect(t, sub, 2*time.Second)

	if len(got) < 2 {
		t.Fatalf("expected at least error+done events, got %d (%v)", len(got), got)
	}
	hasError := false
	hasDone := false
	for _, ev := range got {
		if strings.HasPrefix(ev.Data, "event: error") {
			hasError = true
		}
		if strings.HasPrefix(ev.Data, "data: [DONE]") {
			hasDone = true
		}
	}
	if !hasError {
		t.Errorf("error event not published; events=%v", got)
	}
	if !hasDone {
		t.Errorf("[DONE] event not published; events=%v", got)
	}
	if st, _ := m.GetStatus("s1"); st != StatusError {
		t.Errorf("status: got %v want error", st)
	}
}

func TestNoPanicOnMissingSession(t *testing.T) {
	m := New()
	if m.IsActive("missing") {
		t.Errorf("IsActive on missing should be false")
	}
	if st, ok := m.GetStatus("missing"); ok || st != "" {
		t.Errorf("GetStatus on missing: got (%q,%v) want (\"\",false)", st, ok)
	}
	if m.Stop("missing") {
		t.Errorf("Stop on missing should return false")
	}
	if _, err := m.Subscribe(context.Background(), "missing"); !errors.Is(err, ErrSessionMissing) {
		t.Errorf("Subscribe on missing: got %v want ErrSessionMissing", err)
	}
}

func TestReplayStripping_NoDuplicates(t *testing.T) {
	m := NewWithGrace(50 * time.Millisecond)
	// Slow source so subscribe sees a partial buffer.
	src := &slowSource{delay: 30 * time.Millisecond, total: 5}
	m.Start("s1", src)
	time.Sleep(50 * time.Millisecond)

	sub, err := m.Subscribe(context.Background(), "s1")
	if err != nil {
		t.Fatalf("Subscribe: %v", err)
	}
	got := collect(t, sub, 2*time.Second)

	if len(got) != 5 {
		t.Fatalf("event count: got %d want 5 (events=%v)", len(got), got)
	}
	// Confirm no duplicates by Seq index.
	seen := map[int]bool{}
	for _, ev := range got {
		if ev.Seq < 0 {
			// replay markers use Seq=-1; they still carry distinct Data
			// values (the buffer is identical), so Seq alone isn't unique
			// for them. We rely on data order+content for replay markers.
			continue
		}
		if seen[ev.Seq] {
			t.Errorf("duplicate seq %d", ev.Seq)
		}
		seen[ev.Seq] = true
	}
}

func TestMultipleSubscribersSeeSameEvents(t *testing.T) {
	m := NewWithGrace(50 * time.Millisecond)
	src := &stringSource{events: []string{"a\n", "b\n", "c\n"}}
	m.Start("s1", src)

	// Subscribe first, then quickly subscribe again before the buffer drains.
	sub1, err := m.Subscribe(context.Background(), "s1")
	if err != nil {
		t.Fatalf("Subscribe 1: %v", err)
	}
	time.Sleep(20 * time.Millisecond)
	sub2, err := m.Subscribe(context.Background(), "s1")
	if err != nil {
		t.Fatalf("Subscribe 2: %v", err)
	}

	var wg sync.WaitGroup
	var got1, got2 []Event
	wg.Add(2)
	go func() {
		defer wg.Done()
		got1 = collect(t, sub1, 2*time.Second)
	}()
	go func() {
		defer wg.Done()
		got2 = collect(t, sub2, 2*time.Second)
	}()
	wg.Wait()

	if len(got1) != 3 {
		t.Errorf("sub1: got %d events want 3 (%v)", len(got1), got1)
	}
	if len(got2) != 3 {
		t.Errorf("sub2: got %d events want 3 (%v)", len(got2), got2)
	}
}

// slowSource emits events with a fixed delay between them.
type slowSource struct {
	delay time.Duration
	total int
}

func (s *slowSource) Next(ctx context.Context, sink func(ev string)) error {
	for i := 0; i < s.total; i++ {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(s.delay):
		}
		sink(fmt.Sprintf("e%d\n", i))
	}
	return nil
}

// TestEvictionCancelledOnNewSubscriber ensures that if a new subscriber
// connects during the grace period, the run is NOT evicted.
func TestEvictionCancelledOnNewSubscriber(t *testing.T) {
	m := NewWithGrace(80 * time.Millisecond)
	src := &stringSource{events: []string{"x\n"}}
	m.Start("s1", src)

	sub, err := m.Subscribe(context.Background(), "s1")
	if err != nil {
		t.Fatalf("Subscribe: %v", err)
	}
	// Drain sub1 to EOF.
	_ = collect(t, sub, 1*time.Second)
	// Now there are zero subscribers on a finished run — eviction armed.
	time.Sleep(40 * time.Millisecond) // partway into grace

	// Re-subscribe BEFORE the grace expires. The pending eviction should
	// be cancelled.
	sub2, err := m.Subscribe(context.Background(), "s1")
	if err != nil {
		t.Fatalf("Subscribe 2: %v", err)
	}
	time.Sleep(120 * time.Millisecond) // longer than grace

	// The run should still be present (because the second subscriber
	// cancelled the eviction timer).
	if _, ok := m.GetStatus("s1"); !ok {
		t.Errorf("run was evicted despite a live subscriber")
	}
	_ = collect(t, sub2, 500*time.Millisecond)
}

// TestConcurrentSubscribersSafe checks for race conditions under
// concurrent Start/Subscribe/Stop. Run with -race.
func TestConcurrentSubscribersSafe(t *testing.T) {
	m := NewWithGrace(50 * time.Millisecond)
	src := &slowSource{delay: 5 * time.Millisecond, total: 20}
	m.Start("s1", src)

	var wg sync.WaitGroup
	var connected int64
	for i := 0; i < 8; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			sub, err := m.Subscribe(context.Background(), "s1")
			if err != nil {
				return
			}
			atomic.AddInt64(&connected, 1)
			_ = collect(t, sub, 1*time.Second)
		}()
	}
	wg.Wait()
	if atomic.LoadInt64(&connected) == 0 {
		t.Errorf("no subscriber ever connected")
	}
}
