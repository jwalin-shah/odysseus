package agentloop

import "testing"

func TestDetectRunawayCall_NoCalls_False(t *testing.T) {
	t.Parallel()
	if got := DetectRunawayCall(map[string]int{}, 15); got != "" {
		t.Fatalf("DetectRunawayCall(empty) = %q, want empty", got)
	}
}

func TestDetectRunawayCall_AtThreshold_True(t *testing.T) {
	t.Parallel()
	freq := map[string]int{
		"bash:ls":           15,
		"web_search:python": 5,
	}
	if got := DetectRunawayCall(freq, 15); got != "bash" {
		t.Fatalf("DetectRunawayCall = %q, want bash", got)
	}
}

func TestDetectRunawayCall_BelowThreshold_False(t *testing.T) {
	t.Parallel()
	freq := map[string]int{
		"bash:ls":           14,
		"web_search:python": 5,
	}
	if got := DetectRunawayCall(freq, 15); got != "" {
		t.Fatalf("DetectRunawayCall = %q, want empty", got)
	}
}

// Threshold must be configurable (Python test_threshold_is_configurable).
func TestDetectRunawayCall_ConfigurableThreshold(t *testing.T) {
	t.Parallel()
	freq := map[string]int{"web_search:python": 5}
	if got := DetectRunawayCall(freq, 5); got != "web_search" {
		t.Fatalf("threshold=5: got %q, want web_search", got)
	}
	if got := DetectRunawayCall(freq, 6); got != "" {
		t.Fatalf("threshold=6: got %q, want empty", got)
	}
}

// Distinct calls to one tool are NOT a runaway (the bug fix from the
// Python test suite).
func TestDetectRunawayCall_DistinctSameTool_NotRunaway(t *testing.T) {
	t.Parallel()
	freq := map[string]int{}
	for i := 0; i < 30; i++ {
		freq["bash:echo "+itoa(i)] = 1
	}
	if got := DetectRunawayCall(freq, 15); got != "" {
		t.Fatalf("DetectRunawayCall = %q, want empty", got)
	}
}
