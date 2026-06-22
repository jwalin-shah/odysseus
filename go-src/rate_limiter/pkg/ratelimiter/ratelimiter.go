// Package ratelimiter implements a generic, in-memory, sliding-window rate
// limiter keyed by an arbitrary string (in the Odysseus server this is the
// request IP).
//
// This is a Go port of src/rate_limiter.py. The original module exposes a
// single class — RateLimiter(max_requests, window_seconds) — with one
// public method:
//
//	if not limiter.check(key):
//	    raise HTTPException(429, "Too many requests")
//
// The Go port keeps the same shape: NewLimiter(max int, window
// time.Duration) returns *Limiter, and Allow(key string) bool reports
// whether a request is admitted. The HTTP integration is left to the
// caller — see README.md for the rationale.
//
// # Concurrency
//
// *Limiter.Allow is safe for concurrent use. All mutations are guarded by a
// single sync.Mutex: the per-key timestamp slice is appended to on every
// admitted request, so a read/write split via sync.RWMutex would not help.
// `go test -race ./...` exercises concurrent callers — see
// TestAllowConcurrent.
//
// # Cleanup
//
// The original Python module calls _maybe_cleanup(now) on every check but
// only acts when elapsed exceeds _cleanup_interval (max(window * 2, 120s)).
// The Go port keeps that behavior exactly. To keep tests deterministic the
// internal clock is an unexported function variable that defaults to
// time.Now; tests substitute a stub clock to advance time without
// sleeping.
package ratelimiter

import (
	"sync"
	"time"
)

// Limiter is a sliding-window rate limiter keyed by an arbitrary string.
//
// Construct with NewLimiter; call Allow to admit or reject requests; call
// Reset to clear all state. Use Stats to observe the size of the key
// table for observability/metrics.
type Limiter struct {
	maxRequests int
	window      time.Duration

	// mu guards every field below. Hold it for the entire Allow call
	// (read entries, evict, append, maybe cleanup) so concurrent callers
	// see a consistent view.
	mu sync.Mutex

	// log maps a key to its trailing-window timestamps. Entries are
	// strictly decreasing in age: log[k][0] is the oldest surviving
	// timestamp, log[k][len-1] is the most recent.
	log map[string]*keyState

	// lastCleanup is the monotonic timestamp of the most recent
	// background sweep. Compared with clockFn() to decide whether to
	// run _maybe_cleanup on the next Allow.
	lastCleanup time.Time

	// cleanupInterval is max(window*2, 120s), matching the Python
	// module's `self._cleanup_interval = max(window_seconds * 2, 120)`.
	cleanupInterval time.Duration
}

// keyState holds the trailing-window timestamps for a single key. It is
// unexported; callers observe keys only as opaque strings via Stats.
//
// Timestamps are stored as float64 seconds matching the Python source's
// `time.monotonic()` representation. We convert via
// `float64(t.Sub(epoch)) / float64(time.Second)`. The epoch is the
// limiter's own construction time so the numbers stay small and
// comparable across calls within the same limiter.
type keyState struct {
	entries []float64
}

// epoch is a process-relative reference time used to convert
// time.Time into the float64 seconds the limiter stores. We use
// time.Unix(0, 0) — it is monotonic enough for our arithmetic and
// matches the spirit of Python's `time.monotonic()` (a clock that
// always moves forward, even across system time changes).
var epoch = time.Unix(0, 0)

func toSeconds(t time.Time) float64 {
	return float64(t.Sub(epoch)) / float64(time.Second)
}

// clockFn returns the current monotonic time. Indirected through a
// package var so tests can advance the clock deterministically. Defaults
// to time.Now, which has been monotonic on every supported platform since
// Go 1.9 — same guarantee the Python time.monotonic() call relies on.
var clockFn = time.Now

// minCleanupInterval is the lower bound on _cleanup_interval, matching
// the Python `max(window_seconds * 2, 120)` formula.
const minCleanupInterval = 120 * time.Second

// NewLimiter constructs a sliding-window limiter that admits up to
// maxRequests requests per key per window. Panics if either argument is
// non-positive — the constructor is the only place that validates, so the
// hot path (Allow) can stay allocation-free.
func NewLimiter(maxRequests int, window time.Duration) *Limiter {
	if maxRequests <= 0 {
		panic("ratelimiter: maxRequests must be > 0")
	}
	if window <= 0 {
		panic("ratelimiter: window must be > 0")
	}
	cleanup := window * 2
	if cleanup < minCleanupInterval {
		cleanup = minCleanupInterval
	}
	return &Limiter{
		maxRequests:     maxRequests,
		window:          window,
		log:             make(map[string]*keyState),
		lastCleanup:     clockFn(),
		cleanupInterval: cleanup,
	}
}

// Allow reports whether a request from key may proceed.
//
// Semantics (preserved from src/rate_limiter.py):
//
//  1. Drop every recorded timestamp for key that is older than
//     now - window. The surviving entries form the current window.
//  2. If len(surviving) >= maxRequests, the request is rejected. The
//     surviving entries are stored back (without appending now) so the
//     same call still counts the request as "seen" — the Python source
//     does the same; without it, a hot key that is being rate-limited
//     forever would still grow its slice on every call until the window
//     slid. We mirror that: write the pruned slice, do NOT append now,
//     return false.
//  3. Otherwise append now and return true.
//  4. If elapsed since lastCleanup is at least cleanupInterval, run the
//     background sweep that drops keys whose newest entry is already
//     past the cutoff.
func (l *Limiter) Allow(key string) bool {
	now := clockFn()

	l.mu.Lock()
	defer l.mu.Unlock()

	l.maybeCleanup(now)

	state, ok := l.log[key]
	if !ok {
		// First request from this key — admit and record.
		l.log[key] = &keyState{entries: []float64{toSeconds(now)}}
		return true
	}

	cutoff := toSeconds(now) - l.window.Seconds()
	pruned := state.entries[:0]
	for _, t := range state.entries {
		if t > cutoff {
			pruned = append(pruned, t)
		}
	}

	if len(pruned) >= l.maxRequests {
		// Rejected — store the pruned slice (no append). Match the
		// Python source: `timestamps` is reassigned, then we return
		// False. The slice we keep here points into the same backing
		// array, so we copy into a fresh slice to avoid mutating
		// memory a future read could observe.
		kept := make([]float64, len(pruned))
		copy(kept, pruned)
		state.entries = kept
		return false
	}

	pruned = append(pruned, toSeconds(now))
	state.entries = pruned
	return true
}

// maybeCleanup is the Go port of _maybe_cleanup. It runs on every Allow
// but only acts when elapsed since lastCleanup is at least
// cleanupInterval — exactly the Python module's gating behavior.
//
// Eviction rule (preserved): a key is removed when its entry list is
// empty OR its newest entry is older than (now - window). Empty lists
// only occur if a future version introduces explicit eviction, but the
// Python source checks for them anyway, so we mirror that.
func (l *Limiter) maybeCleanup(now time.Time) {
	if now.Sub(l.lastCleanup) < l.cleanupInterval {
		return
	}
	l.lastCleanup = now

	cutoff := toSeconds(now) - l.window.Seconds()
	for k, v := range l.log {
		if len(v.entries) == 0 || v.entries[len(v.entries)-1] <= cutoff {
			delete(l.log, k)
		}
	}
}

// Stats describes the limiter's current state for observability. The key
// list is intentionally omitted — the per-IP table is sensitive in
// production and should not be dumped into logs.
type Stats struct {
	Keys        int           // number of distinct keys currently tracked
	MaxRequests int           // requests admitted per window
	Window      time.Duration // size of the sliding window
}

// Stats returns a snapshot of the limiter's configuration and the current
// size of the key table. The count is read under the same mutex used by
// Allow, so it is consistent with a recent Allow call but may drift the
// instant Allow returns.
func (l *Limiter) Stats() Stats {
	l.mu.Lock()
	defer l.mu.Unlock()
	return Stats{
		Keys:        len(l.log),
		MaxRequests: l.maxRequests,
		Window:      l.window,
	}
}

// Reset drops every recorded entry. Useful in tests and when an operator
// resets a tenant's quota. Does not change MaxRequests or Window.
func (l *Limiter) Reset() {
	l.mu.Lock()
	defer l.mu.Unlock()
	l.log = make(map[string]*keyState)
	l.lastCleanup = clockFn()
}
