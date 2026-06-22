package ratelimiter

import (
	"fmt"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// withClock runs fn with the package clockFn rebound to a fake clock that
// starts at start and advances by step on every call. The original clock
// is restored when fn returns. Tests use this to drive deterministic
// eviction/cleanup behavior without sleeping.
//
// The fake returns time.Time values that are valid monotonic-clock
// values; the limiter only does arithmetic on them so it does not care
// that the wall-clock component is fictional.
func withClock(t *testing.T, start time.Time, step time.Duration, fn func(advance func(time.Duration))) {
	t.Helper()
	orig := clockFn
	t.Cleanup(func() { clockFn = orig })

	var cur int64 // atomic ns since start
	set := func(d time.Duration) {
		atomic.StoreInt64(&cur, int64(d))
	}
	clockFn = func() time.Time {
		return start.Add(time.Duration(atomic.LoadInt64(&cur)))
	}

	// Replace the limiter's lastCleanup with a clockFn read so any
	// pre-construction state stays consistent.
	set(0)
	fn(set)
}

// TestNewLimiterPanicsOnZeroOrNegative pins the constructor's validation
// behavior. The Python module does not validate; the Go port panics
// because passing max=0 or window=0 silently disables the limiter.
func TestNewLimiterPanicsOnZeroOrNegative(t *testing.T) {
	cases := []struct {
		name string
		max  int
		win  time.Duration
	}{
		{"zero max", 0, time.Second},
		{"negative max", -1, time.Second},
		{"zero window", 5, 0},
		{"negative window", 5, -time.Second},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			defer func() {
				if r := recover(); r == nil {
					t.Fatalf("expected panic for max=%d win=%v, got none", tc.max, tc.win)
				}
			}()
			_ = NewLimiter(tc.max, tc.win)
		})
	}
}

// TestCleanupInterval pins the formula:
//
//	max(window * 2, 120s)
//
// The Python source is `max(window_seconds * 2, 120)`. Anything below 60s
// must round up to 120s; anything at or above 60s uses 2*window.
func TestCleanupInterval(t *testing.T) {
	cases := []struct {
		window time.Duration
		want   time.Duration
	}{
		{1 * time.Second, 120 * time.Second},  // 2s < 120s
		{30 * time.Second, 120 * time.Second}, // 60s < 120s
		{60 * time.Second, 120 * time.Second}, // 120s == 120s
		{61 * time.Second, 122 * time.Second}, // 122s > 120s
		{10 * time.Minute, 20 * time.Minute},  // large windows
	}
	for _, tc := range cases {
		t.Run(tc.window.String(), func(t *testing.T) {
			lm := NewLimiter(5, tc.window)
			if lm.cleanupInterval != tc.want {
				t.Errorf("cleanupInterval=%v, want %v", lm.cleanupInterval, tc.want)
			}
		})
	}
}

// TestAllowAdmitsUpToMaxThenRejects is the core happy-path test: the
// first N requests for a single key pass, the (N+1)th is rejected.
func TestAllowAdmitsUpToMaxThenRejects(t *testing.T) {
	lm := NewLimiter(5, time.Minute)

	for i := 1; i <= 5; i++ {
		if !lm.Allow("ip-a") {
			t.Fatalf("request %d should be admitted", i)
		}
	}
	if lm.Allow("ip-a") {
		t.Fatal("6th request should be rejected")
	}
}

// TestAllowIsPerKey verifies that one key hitting its limit does not
// affect other keys. Mirrors the Python `self._log.get(key, [])` lookup.
func TestAllowIsPerKey(t *testing.T) {
	lm := NewLimiter(2, time.Minute)

	for i := 0; i < 2; i++ {
		if !lm.Allow("ip-a") {
			t.Fatalf("ip-a request %d should be admitted", i+1)
		}
	}
	if lm.Allow("ip-a") {
		t.Fatal("ip-a should be rate-limited after 2 requests")
	}
	// Different keys are independent.
	for _, k := range []string{"ip-b", "ip-c", "ip-d"} {
		if !lm.Allow(k) {
			t.Errorf("%s first request should be admitted", k)
		}
	}
}

// TestAllowRejectionDoesNotAppend pins the subtle detail in the Python
// source: when the request is rejected, the current timestamp is NOT
// appended to the entry list. Without this property, a hot key under
// sustained pressure would keep growing its slice until the window slid.
func TestAllowRejectionDoesNotAppend(t *testing.T) {
	lm := NewLimiter(1, time.Minute)

	if !lm.Allow("k") {
		t.Fatal("first call must be admitted")
	}
	if lm.Allow("k") {
		t.Fatal("second call must be rejected")
	}

	lm.mu.Lock()
	state := lm.log["k"]
	lm.mu.Unlock()
	if got := len(state.entries); got != 1 {
		t.Fatalf("entries=%d, want 1 (rejection must not append)", got)
	}
}

// TestAllowWindowSlides is the sliding-window core. With max=3 and
// window=10s, 3 requests in [0,10s] are admitted; the 4th is rejected.
// After we advance the clock past 10s the window slides and the next
// request is admitted.
func TestAllowWindowSlides(t *testing.T) {
	withClock(t, time.Unix(0, 0), time.Second, func(advance func(time.Duration)) {
		lm := NewLimiter(3, 10*time.Second)

		for i := 1; i <= 3; i++ {
			if !lm.Allow("k") {
				t.Fatalf("call %d should be admitted", i)
			}
		}
		if lm.Allow("k") {
			t.Fatal("4th call inside window should be rejected")
		}

		// Slide the window past the original three timestamps.
		advance(11 * time.Second)
		if !lm.Allow("k") {
			t.Fatal("call after window slide should be admitted")
		}
	})
}

// TestAllowPrunesStaleEntries verifies that the per-key entry slice is
// pruned on every Allow so it does not grow unboundedly across many
// windows.
func TestAllowPrunesStaleEntries(t *testing.T) {
	withClock(t, time.Unix(0, 0), time.Second, func(advance func(time.Duration)) {
		lm := NewLimiter(5, 10*time.Second)

		for i := 1; i <= 5; i++ {
			if !lm.Allow("k") {
				t.Fatalf("call %d should be admitted", i)
			}
		}

		// Slide well past the window. Next call should prune all 5
		// entries to zero, then admit a single new entry.
		advance(20 * time.Second)
		if !lm.Allow("k") {
			t.Fatal("call after window slide should be admitted")
		}

		lm.mu.Lock()
		state := lm.log["k"]
		lm.mu.Unlock()
		if got := len(state.entries); got != 1 {
			t.Fatalf("after slide, entries=%d, want 1", got)
		}
	})
}

// TestAllowCleanupEvictsStaleKeys verifies the Python
// `_maybe_cleanup` behavior: after cleanupInterval elapses, keys whose
// newest entry is older than (now - window) are removed.
func TestAllowCleanupEvictsStaleKeys(t *testing.T) {
	withClock(t, time.Unix(0, 0), time.Second, func(advance func(time.Duration)) {
		lm := NewLimiter(5, 10*time.Second)

		// Prime two keys at t=0.
		lm.Allow("hot")
		lm.Allow("cold")

		// Advance past the cleanup interval (2*window = 20s, but the
		// minimum is 120s — same as the Python source). Use the
		// minimum so the test does not have to sleep.
		advance(121 * time.Second)

		// Trigger a cleanup by calling Allow on a fresh key.
		lm.Allow("trigger")

		// "hot" and "cold" had their last entry at t=0; cutoff is
		// now - 10s = 111s, so 0 <= 111 and they are stale.
		lm.mu.Lock()
		_, hasHot := lm.log["hot"]
		_, hasCold := lm.log["cold"]
		_, hasTrigger := lm.log["trigger"]
		lm.mu.Unlock()

		if hasHot {
			t.Error("hot should have been evicted by cleanup")
		}
		if hasCold {
			t.Error("cold should have been evicted by cleanup")
		}
		if !hasTrigger {
			t.Error("trigger must survive cleanup (newest entry at t=121s)")
		}
	})
}

// TestAllowCleanupSkipsBeforeInterval confirms the cleanup gate: before
// cleanupInterval elapses, stale keys are NOT evicted on Allow.
func TestAllowCleanupSkipsBeforeInterval(t *testing.T) {
	withClock(t, time.Unix(0, 0), time.Second, func(advance func(time.Duration)) {
		lm := NewLimiter(5, 10*time.Second)

		lm.Allow("stale")
		// Below the 120s minimum cleanup interval. cleanup must skip.
		advance(60 * time.Second)
		lm.Allow("trigger")

		lm.mu.Lock()
		_, hasStale := lm.log["stale"]
		lm.mu.Unlock()
		if !hasStale {
			t.Error("stale key must survive when cleanup has not yet run")
		}
	})
}

// TestAllowWindowDoesNotSlideForRejectedRequests pins a subtle
// interaction: even when rejected, the window slides as expected —
// because the pruning pass discards entries older than cutoff
// regardless of whether the call is admitted.
func TestAllowWindowDoesNotSlideForRejectedRequests(t *testing.T) {
	withClock(t, time.Unix(0, 0), time.Second, func(advance func(time.Duration)) {
		lm := NewLimiter(1, 10*time.Second)

		lm.Allow("k") // t=0, admitted
		if lm.Allow("k") {
			t.Fatal("call 2 must be rejected (1/10s)")
		}

		advance(11 * time.Second)
		if !lm.Allow("k") {
			t.Fatal("after window slide, call should be admitted again")
		}
	})
}

// TestStatsReportsConfiguration pins Stats(). Uses a real clock but
// only calls Allow on distinct keys so we can assert Key count.
func TestStatsReportsConfiguration(t *testing.T) {
	lm := NewLimiter(7, 30*time.Second)

	stats := lm.Stats()
	if stats.MaxRequests != 7 {
		t.Errorf("MaxRequests=%d, want 7", stats.MaxRequests)
	}
	if stats.Window != 30*time.Second {
		t.Errorf("Window=%v, want 30s", stats.Window)
	}
	if stats.Keys != 0 {
		t.Errorf("Keys=%d, want 0 (no calls yet)", stats.Keys)
	}

	for _, k := range []string{"a", "b", "c"} {
		lm.Allow(k)
	}
	stats = lm.Stats()
	if stats.Keys != 3 {
		t.Errorf("Keys=%d, want 3", stats.Keys)
	}
}

// TestResetClearsTable verifies that Reset drops every entry without
// changing MaxRequests or Window.
func TestResetClearsTable(t *testing.T) {
	lm := NewLimiter(2, time.Minute)
	lm.Allow("a")
	lm.Allow("b")

	lm.Reset()

	if stats := lm.Stats(); stats.Keys != 0 {
		t.Errorf("after Reset, Keys=%d, want 0", stats.Keys)
	}
	// Configuration is preserved.
	if stats := lm.Stats(); stats.MaxRequests != 2 || stats.Window != time.Minute {
		t.Errorf("Reset changed configuration: %+v", stats)
	}
	// After reset, every key gets a fresh budget.
	for i := 0; i < 2; i++ {
		if !lm.Allow("a") {
			t.Fatalf("post-reset call %d should be admitted", i+1)
		}
	}
}

// TestAllowConcurrent races many goroutines through the limiter. The
// race detector must report no warnings. We do not assert exact
// admission counts because the window is wide enough that all calls
// fit; we only assert correctness under concurrent stress.
func TestAllowConcurrent(t *testing.T) {
	lm := NewLimiter(10000, time.Minute)

	const goroutines = 32
	const perGoroutine = 200

	var wg sync.WaitGroup
	for g := 0; g < goroutines; g++ {
		wg.Add(1)
		go func(g int) {
			defer wg.Done()
			key := fmt.Sprintf("g%d", g%4) // 4 distinct keys
			for i := 0; i < perGoroutine; i++ {
				lm.Allow(key)
			}
		}(g)
	}
	wg.Wait()

	// 32 goroutines mod 4 keys = 8 goroutines per key, each making
	// 200 calls -> 1600 admits per key. max=10000 + 1-minute window
	// means none of those calls were rejected, so every entry is
	// recorded.
	wantPerKey := (goroutines / 4) * perGoroutine
	for _, k := range []string{"g0", "g1", "g2", "g3"} {
		lm.mu.Lock()
		state := lm.log[k]
		lm.mu.Unlock()
		if state == nil {
			t.Errorf("key %s missing from log after concurrent admits", k)
			continue
		}
		if got := len(state.entries); got != wantPerKey {
			t.Errorf("key %s has %d entries, want %d", k, got, wantPerKey)
		}
	}
}

// TestAllowConcurrentStaleEviction exercises concurrent Allow + cleanup.
// Each goroutine admits a key, then we advance the clock past the
// cleanup interval and admit on a fresh key. The race detector is the
// proof; we only check that the table ends up with just the trigger
// key.
func TestAllowConcurrentStaleEviction(t *testing.T) {
	withClock(t, time.Unix(0, 0), time.Second, func(advance func(time.Duration)) {
		lm := NewLimiter(5, 10*time.Second)

		var wg sync.WaitGroup
		const goroutines = 16
		for g := 0; g < goroutines; g++ {
			wg.Add(1)
			go func(g int) {
				defer wg.Done()
				lm.Allow(fmt.Sprintf("k%d", g))
			}(g)
		}
		wg.Wait()

		// Advance past cleanup interval.
		advance(121 * time.Second)
		lm.Allow("trigger")

		lm.mu.Lock()
		keys := make([]string, 0, len(lm.log))
		for k := range lm.log {
			keys = append(keys, k)
		}
		lm.mu.Unlock()

		if len(keys) != 1 || keys[0] != "trigger" {
			t.Errorf("after cleanup, log=%v, want only [trigger]", keys)
		}
	})
}

// TestAllowHotKeyStaysAtMaxNotBeyond confirms the documented Python
// behavior: at exactly maxRequests requests in the window the (N+1)th
// call is rejected, but N+0 calls all pass — i.e. the comparison is
// >=, matching `if len(timestamps) >= self.max_requests`.
func TestAllowHotKeyStaysAtMaxNotBeyond(t *testing.T) {
	lm := NewLimiter(3, time.Minute)

	for i := 0; i < 3; i++ {
		if !lm.Allow("hot") {
			t.Fatalf("request %d must be admitted", i+1)
		}
	}
	// 4th must reject.
	for i := 0; i < 5; i++ {
		if lm.Allow("hot") {
			t.Fatalf("request %d (post-limit) must be rejected", i+4)
		}
	}
}
