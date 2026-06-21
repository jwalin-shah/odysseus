package research_utils

import (
	"strings"
	"testing"
)

func TestIsLowQuality_Empty(t *testing.T) {
	if !IsLowQuality("") {
		t.Fatalf("empty string should be low quality")
	}
}

func TestIsLowQuality_WhitespaceOnly(t *testing.T) {
	// Python: `not summary` is False for whitespace, so returns based on
	// markers. With no markers present, returns false. Match Python.
	if IsLowQuality("   \n\t  ") {
		t.Fatalf("whitespace-only input with no markers should not be low quality")
	}
}

func TestIsLowQuality_EachMarker(t *testing.T) {
	markers := []string{
		"insufficient to",
		"content is insufficient",
		"no substantive data",
		"does not contain",
		"not relevant to",
		"no relevant information",
		"unable to extract",
		"completely unrelated",
		"boilerplate",
		"footer text",
		"cookie consent",
		"cookie banner",
		"cookie notice",
		"copyright notice",
		"copyright footer",
		"all rights reserved",
	}
	if len(markers) != len(LowQualityMarkers) {
		t.Fatalf("test marker list out of sync: have %d, want %d", len(markers), len(LowQualityMarkers))
	}
	for i, m := range markers {
		// Use a phrasing that contains the marker as a substring.
		input := "summary body — " + m + " — end"
		if !IsLowQuality(input) {
			t.Errorf("marker %d %q: expected low quality, got false", i, m)
		}
	}
}

func TestIsLowQuality_CaseInsensitive(t *testing.T) {
	if !IsLowQuality("UPPERCASE COOKIE CONSENT TEXT") {
		t.Fatalf("uppercase marker should be detected (case-insensitive)")
	}
}

func TestIsLowQuality_MarkerAsSubstring(t *testing.T) {
	// Marker is a phrase and is detected as a substring of larger text.
	long := strings.Repeat("filler ", 50) + "no relevant information here"
	if !IsLowQuality(long) {
		t.Fatalf("marker as substring of larger text should be detected")
	}
}

func TestIsLowQuality_CleanText(t *testing.T) {
	if IsLowQuality("This is a clean, well-formed research finding about neural network architectures.") {
		t.Fatalf("clean text should not be low quality")
	}
}

func TestIsLowQuality_MarkerNotAsSubstring(t *testing.T) {
	// Markers are phrases, not bare words — "cookies" must not trigger
	// "cookie consent" detection, etc.
	cases := []string{
		"We discussed cookies and recipes in the meeting.",
		"The copyright law is complex and evolving.",
		"Reserved parking is available on the left.",
		"This is unrelated material that contains none of the markers.",
	}
	for _, c := range cases {
		// The first three must be clean. The fourth contains the bare
		// word "boilerplate" without any of the actual markers appearing
		// as a substring.
		if IsLowQuality(c) {
			t.Errorf("case %q: expected not low quality, got true", c)
		}
	}
}

func TestIsLowQuality_FailureMode_NoPanic(t *testing.T) {
	// Strange inputs must not panic — the deferred recover in IsLowQuality
	// will swallow any panic and return false.
	cases := []string{
		strings.Repeat("a", 1<<16),
		"contains null \x00 byte in the middle",
		"control \x07 \x08 \x0b chars",
		strings.Repeat("​", 1000), // zero-width spaces
		"mixed \xff\xfe\xfd bytes",
	}
	for _, c := range cases {
		_ = IsLowQuality(c)
	}
}

func TestLowQualityMarkers_ExactContents(t *testing.T) {
	want := []string{
		"insufficient to",
		"content is insufficient",
		"no substantive data",
		"does not contain",
		"not relevant to",
		"no relevant information",
		"unable to extract",
		"completely unrelated",
		"boilerplate",
		"footer text",
		"cookie consent",
		"cookie banner",
		"cookie notice",
		"copyright notice",
		"copyright footer",
		"all rights reserved",
	}
	if len(LowQualityMarkers) != len(want) {
		t.Fatalf("LowQualityMarkers length = %d, want %d", len(LowQualityMarkers), len(want))
	}
	for i := range want {
		if LowQualityMarkers[i] != want[i] {
			t.Errorf("LowQualityMarkers[%d] = %q, want %q", i, LowQualityMarkers[i], want[i])
		}
	}
}

func TestStripThinking_NilInput(t *testing.T) {
	if StripThinking(nil) != nil {
		t.Fatalf("nil input must return nil")
	}
}

func TestStripThinking_EmptyString(t *testing.T) {
	empty := ""
	out := StripThinking(&empty)
	if out == nil {
		t.Fatalf("empty string input should return non-nil empty output, got nil")
	}
	if *out != "" {
		t.Fatalf("empty string input should return empty output, got %q", *out)
	}
}

func TestStripThinking_NoPatterns(t *testing.T) {
	in := "The capital of France is Paris. It is known for the Eiffel Tower."
	out := StripThinking(&in)
	if out == nil || *out != in {
		t.Fatalf("clean text should be unchanged, got %q", *out)
	}
}

func TestStripThinking_ThinkingBlock(t *testing.T) {
	in := "Before text <thinking>internal chain of thought</thinking> after text."
	out := StripThinking(&in)
	if out == nil {
		t.Fatalf("got nil output")
	}
	if strings.Contains(*out, "<thinking>") || strings.Contains(*out, "internal chain of thought") {
		t.Fatalf("thinking block not stripped: %q", *out)
	}
	if !strings.Contains(*out, "Before text") || !strings.Contains(*out, "after text") {
		t.Fatalf("surrounding text was damaged: %q", *out)
	}
}

func TestStripThinking_ReasoningBlock(t *testing.T) {
	in := "Hello <reasoning>step 1 step 2</reasoning> world."
	out := StripThinking(&in)
	if out == nil {
		t.Fatalf("got nil output")
	}
	if strings.Contains(*out, "<reasoning>") || strings.Contains(*out, "step 1") {
		t.Fatalf("reasoning block not stripped: %q", *out)
	}
}

func TestStripThinking_ThoughtPrefix(t *testing.T) {
	in := "Thought: this is a thought line\nReal answer is 42."
	out := StripThinking(&in)
	if out == nil {
		t.Fatalf("got nil output")
	}
	if strings.Contains(*out, "Thought:") {
		t.Fatalf("Thought: prefix not stripped: %q", *out)
	}
	if !strings.Contains(*out, "Real answer is 42.") {
		t.Fatalf("real content was damaged: %q", *out)
	}
}

func TestStripThinking_ReasoningPrefix(t *testing.T) {
	in := "Reasoning: the model thought step by step\nResult: 7."
	out := StripThinking(&in)
	if out == nil {
		t.Fatalf("got nil output")
	}
	if strings.Contains(*out, "Reasoning:") {
		t.Fatalf("Reasoning: prefix not stripped: %q", *out)
	}
}

func TestStripThinking_MultiplePatterns(t *testing.T) {
	in := "Before.\n<thinking>hidden thought</thinking>\n" +
		"Thought: another thought\n" +
		"Middle.\n" +
		"<reasoning>more hidden</reasoning>\n" +
		"After."
	out := StripThinking(&in)
	if out == nil {
		t.Fatalf("got nil output")
	}
	for _, bad := range []string{"<thinking>", "<reasoning>", "hidden thought", "another thought", "more hidden", "Thought:", "Reasoning:"} {
		if strings.Contains(*out, bad) {
			t.Errorf("expected %q to be stripped, but it remains in: %q", bad, *out)
		}
	}
	for _, good := range []string{"Before.", "Middle.", "After."} {
		if !strings.Contains(*out, good) {
			t.Errorf("expected %q to remain, but it is missing from: %q", good, *out)
		}
	}
}

func TestStripThinking_MalformedTagsNoCrash(t *testing.T) {
	cases := []string{
		"<thinking>never closed",
		"</thinking>orphan close",
		"<<<>>>broken",
		"<thinking><thinking>nested</thinking></thinking>",
		"<>empty</>",
		"<thinking></thinking>",
	}
	for _, c := range cases {
		// Must not panic. Output is best-effort.
		out := StripThinking(&c)
		if out == nil {
			t.Errorf("case %q: got nil output", c)
		}
	}
}

func TestStripThinking_QuoteBlockReasoning(t *testing.T) {
	in := "Real intro.\n> I think this is a reasoning trace line\nReal conclusion."
	out := StripThinking(&in)
	if out == nil {
		t.Fatalf("got nil output")
	}
	if strings.Contains(*out, "I think this is a reasoning trace line") {
		t.Fatalf("quote reasoning line not stripped: %q", *out)
	}
	if !strings.Contains(*out, "Real intro.") || !strings.Contains(*out, "Real conclusion.") {
		t.Fatalf("real content damaged: %q", *out)
	}
}
