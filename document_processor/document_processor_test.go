package document_processor

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// --- IsTextFile -----------------------------------------------------------

func TestIsTextFile_True(t *testing.T) {
	for _, ext := range []string{".txt", ".py", ".html", ".htm", ".md", ".json", ".csv", ".log", ".js", ".nix"} {
		path := "example" + ext
		if !IsTextFile(path) {
			t.Errorf("IsTextFile(%q) = false, want true", path)
		}
		// Case insensitivity — the Python version lowercases before
		// checking.
		if !IsTextFile(strings.ToUpper("example" + ext)) {
			t.Errorf("IsTextFile(%q) = false, want true (case-insensitive)", strings.ToUpper("example"+ext))
		}
	}
}

func TestIsTextFile_False(t *testing.T) {
	for _, ext := range []string{".pdf", ".png", ".docx", ".zip", ".tar", ""} {
		path := "example" + ext
		if IsTextFile(path) {
			t.Errorf("IsTextFile(%q) = true, want false", path)
		}
	}
}

// --- LanguageFor ----------------------------------------------------------

func TestLanguageFor_KnownAndUnknown(t *testing.T) {
	cases := []struct {
		path string
		want string
	}{
		{"hello.py", "python"},
		{"hello.js", "javascript"},
		{"hello.tsx", "typescript"},
		{"hello.html", "html"},
		{"hello.json", "json"},
		{"hello.md", "markdown"},
		{"hello.txt", "text"},
		{"hello.csv", "csv"},
		{"hello.log", "log"},
		{"hello.yml", "yaml"},
		{"hello.unknown", "text"},
		{"HELLO.PY", "python"}, // case-insensitive
	}
	for _, tc := range cases {
		t.Run(tc.path, func(t *testing.T) {
			if got := LanguageFor(tc.path); got != tc.want {
				t.Errorf("LanguageFor(%q) = %q, want %q", tc.path, got, tc.want)
			}
		})
	}
}

// --- IsCodeExtension ------------------------------------------------------

func TestIsCodeExtension(t *testing.T) {
	for _, ext := range []string{".py", ".go", ".js", ".tsx", ".rs", ".md", ".sh"} {
		if !IsCodeExtension(ext) {
			t.Errorf("IsCodeExtension(%q) = false, want true", ext)
		}
	}
	for _, ext := range []string{".txt", ".csv", ".log", ".pdf", ""} {
		if IsCodeExtension(ext) {
			t.Errorf("IsCodeExtension(%q) = true, want false", ext)
		}
	}
}

// --- StripPDFContentMarker ------------------------------------------------

func TestStripPDFContentMarker_RemovesPrefix(t *testing.T) {
	in := "\n\n[PDF content]:\n\n[Page 1 text]:\nto the board"
	got := StripPDFContentMarker(in)
	if strings.HasPrefix(got, "[PDF content]") {
		t.Errorf("marker still present: %q", got)
	}
	if !strings.Contains(got, "to the board") {
		t.Errorf("body content lost: %q", got)
	}
	if strings.HasPrefix(got, "to ") || strings.HasPrefix(got, "the") {
		// Specifically: lstrip on the marker would have eaten 't','o' etc.
		t.Errorf("lstrip-style damage to body: %q", got)
	}
}

func TestStripPDFContentMarker_NoMarker(t *testing.T) {
	in := "nothing here\nto see"
	got := StripPDFContentMarker(in)
	if got != "nothing here\nto see" {
		t.Errorf("got %q, want %q", got, "nothing here\nto see")
	}
}

func TestStripPDFContentMarker_EmptyInput(t *testing.T) {
	if got := StripPDFContentMarker(""); got != "" {
		t.Errorf("StripPDFContentMarker(\"\") = %q, want \"\"", got)
	}
}

// --- TruncateInline -------------------------------------------------------

func TestTruncateInline_NoTruncation(t *testing.T) {
	body, marker := TruncateInline("hello world", 100)
	if body != "hello world" {
		t.Errorf("body = %q, want %q", body, "hello world")
	}
	if marker != "" {
		t.Errorf("marker = %q, want empty", marker)
	}
}

func TestTruncateInline_OverLimitReturnsMarker(t *testing.T) {
	long := strings.Repeat("a", 200)
	body, marker := TruncateInline(long, 50)
	if body != strings.Repeat("a", 50) {
		t.Errorf("body length = %d, want 50", len(body))
	}
	if marker == "" {
		t.Errorf("marker = empty, want truncation marker")
	}
	if !strings.Contains(marker, "truncated") {
		t.Errorf("marker %q should mention truncation", marker)
	}
}

func TestTruncateInline_StripsLeadingTrailingWhitespace(t *testing.T) {
	body, _ := TruncateInline("   hello world   ", 100)
	if body != "hello world" {
		t.Errorf("body = %q, want %q (whitespace not stripped)", body, "hello world")
	}
}

// --- FitInlineAttachmentText ---------------------------------------------

func TestFitInlineAttachmentText_FitsWithinBudget(t *testing.T) {
	body, remaining := FitInlineAttachmentText("hello world", 100, "doc.txt")
	if body != "hello world" {
		t.Errorf("body = %q, want %q", body, "hello world")
	}
	if remaining != 89 {
		t.Errorf("remaining = %d, want 89", remaining)
	}
}

func TestFitInlineAttachmentText_ZeroRemaining(t *testing.T) {
	body, remaining := FitInlineAttachmentText("hello world", 0, "doc.txt")
	if remaining != 0 {
		t.Errorf("remaining = %d, want 0", remaining)
	}
	if !strings.Contains(body, "omitted from inline context") {
		t.Errorf("body should be the omitted placeholder, got %q", body)
	}
	if !strings.Contains(body, "doc.txt") {
		t.Errorf("placeholder should mention display name, got %q", body)
	}
}

func TestFitInlineAttachmentText_BelowMinSlice(t *testing.T) {
	// Body is longer than the remaining budget but the remaining budget
	// itself is below MinInlineAttachmentSlice — placeholder path.
	body, remaining := FitInlineAttachmentText(strings.Repeat("x", 1000), MinInlineAttachmentSlice-1, "doc.txt")
	if remaining != 0 {
		t.Errorf("remaining = %d, want 0", remaining)
	}
	if !strings.Contains(body, "omitted from inline context") {
		t.Errorf("body should be the omitted placeholder, got %q", body)
	}
	if !strings.Contains(body, "doc.txt") {
		t.Errorf("placeholder should mention display name, got %q", body)
	}
}

func TestFitInlineAttachmentText_TruncatesWhenSliceAvailable(t *testing.T) {
	// Body is longer than remaining AND remaining is at or above the
	// min-slice threshold — truncation marker path.
	body, remaining := FitInlineAttachmentText(strings.Repeat("x", 2000), MinInlineAttachmentSlice, "doc.txt")
	if remaining != 0 {
		t.Errorf("remaining = %d, want 0", remaining)
	}
	if !strings.Contains(body, "truncated") {
		t.Errorf("body should be the truncation marker, got %q", body)
	}
	if !strings.Contains(body, "doc.txt") {
		t.Errorf("marker should mention display name, got %q", body)
	}
}

func TestFitInlineAttachmentText_MissingDisplayName(t *testing.T) {
	body, _ := FitInlineAttachmentText("hello world", 0, "")
	if !strings.Contains(body, "attachment") {
		t.Errorf("body should default to 'attachment' name, got %q", body)
	}
}

// --- ProcessTextFile ------------------------------------------------------

// writeTemp is a small helper that drops content into a temp file with the
// given extension and returns the path. The caller is responsible for
// removing the file (we use t.TempDir so it's automatic).
func writeTemp(t *testing.T, name, content string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), name)
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write temp: %v", err)
	}
	return path
}

func TestProcessTextFile_RejectsNonText(t *testing.T) {
	path := writeTemp(t, "blob.pdf", "not a text file")
	_, err := ProcessTextFile(path)
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !errors.Is(err, ErrNotTextFile) {
		t.Errorf("expected ErrNotTextFile, got %v", err)
	}
}

func TestProcessTextFile_PythonFileFencedBlock(t *testing.T) {
	body := "def hi():\n    print('hello')\n"
	path := writeTemp(t, "hello.py", body)
	got, err := ProcessTextFile(path)
	if err != nil {
		t.Fatalf("ProcessTextFile: %v", err)
	}

	wantLines := []string{
		"\n=== File: hello.py ===",
		"[Type: python, Lines: 3, Size: " + humanInt(int64(len(body))) + " bytes]",
		"```python",
		body,
		"```",
	}
	for i, want := range wantLines {
		if !strings.Contains(got, want) {
			t.Errorf("missing line %d (%q) in output:\n%s", i, want, got)
		}
	}
}

func TestProcessTextFile_TxtFileRawContent(t *testing.T) {
	body := "alpha\nbeta\ngamma\n"
	path := writeTemp(t, "notes.txt", body)
	got, err := ProcessTextFile(path)
	if err != nil {
		t.Fatalf("ProcessTextFile: %v", err)
	}
	if strings.Contains(got, "```") {
		t.Errorf("plain text should NOT be fenced, got:\n%s", got)
	}
	if !strings.Contains(got, "[Type: text, Lines: 4, Size: "+
		humanInt(int64(len(body)))+" bytes]") {
		t.Errorf("missing or wrong header line, got:\n%s", got)
	}
	if !strings.Contains(got, "alpha\nbeta\ngamma") {
		t.Errorf("body content missing, got:\n%s", got)
	}
}

func TestProcessTextFile_TruncatesAt30000(t *testing.T) {
	// Build content of ~31000 chars; the cap is 30000.
	body := strings.Repeat("a", 31000)
	path := writeTemp(t, "big.txt", body)
	got, err := ProcessTextFile(path)
	if err != nil {
		t.Fatalf("ProcessTextFile: %v", err)
	}
	if !strings.HasSuffix(got, "[Truncated]") {
		t.Errorf("expected [Truncated] marker at end, got suffix:\n%s", got[len(got)-200:])
	}
	// The body section should be capped to <= 30000 (the truncation may snap
	// back to an earlier newline if one exists nearby, but no newline
	// exists so it should be exactly maxLen).
	bodyStart := strings.Index(got, "\n\n")
	if bodyStart < 0 {
		t.Fatalf("could not locate body start in:\n%s", got)
	}
	bodyOnly := got[bodyStart+2:]
	bodyOnly = strings.TrimSuffix(bodyOnly, "\n[Truncated]")
	if len(bodyOnly) > 30000 {
		t.Errorf("body length = %d, want <= 30000", len(bodyOnly))
	}
}

func TestProcessTextFile_TruncationRespectsNewline(t *testing.T) {
	// 29990 chars of filler + "\n" + 100 chars more. The truncation
	// forward search should snap to the newline at offset 29990.
	body := strings.Repeat("a", 29990) + "\n" + strings.Repeat("b", 100)
	path := writeTemp(t, "snapped.txt", body)
	got, err := ProcessTextFile(path)
	if err != nil {
		t.Fatalf("ProcessTextFile: %v", err)
	}
	if !strings.HasSuffix(got, "[Truncated]") {
		t.Errorf("expected [Truncated] marker at end, got suffix:\n%s", got[len(got)-200:])
	}
	// The body should NOT contain any 'b' characters — truncation snapped
	// to the newline at 29990.
	bodyStart := strings.Index(got, "\n\n")
	if bodyStart < 0 {
		t.Fatalf("could not locate body start in:\n%s", got)
	}
	bodyOnly := got[bodyStart+2:]
	if strings.Contains(bodyOnly, "b") {
		t.Errorf("body contains 'b' characters past the newline; truncation didn't snap:\n%s", bodyOnly[len(bodyOnly)-300:])
	}
}

func TestProcessTextFile_LogCapsAt10000(t *testing.T) {
	body := strings.Repeat("x", 12000)
	path := writeTemp(t, "server.log", body)
	got, err := ProcessTextFile(path)
	if err != nil {
		t.Fatalf("ProcessTextFile: %v", err)
	}
	if !strings.HasSuffix(got, "[Truncated]") {
		t.Errorf("expected [Truncated] marker, got suffix:\n%s", got[len(got)-200:])
	}
	bodyStart := strings.Index(got, "\n\n")
	if bodyStart < 0 {
		t.Fatalf("could not locate body start")
	}
	bodyOnly := got[bodyStart+2:]
	bodyOnly = strings.TrimSuffix(bodyOnly, "\n[Truncated]")
	if len(bodyOnly) > 10000 {
		t.Errorf("log body length = %d, want <= 10000", len(bodyOnly))
	}
}

func TestProcessTextFile_NonUTF8ReplacedWithReplacementChar(t *testing.T) {
	// 0xff is not valid UTF-8 by itself. The package should not panic and
	// should return a string containing the replacement character.
	path := writeTemp(t, "weird.txt", "\xff\xfeabc")
	got, err := ProcessTextFile(path)
	if err != nil {
		t.Fatalf("ProcessTextFile: %v", err)
	}
	if !strings.Contains(got, "abc") {
		t.Errorf("expected 'abc' to survive, got:\n%s", got)
	}
	if !strings.Contains(got, "�") {
		t.Errorf("expected U+FFFD replacement char, got:\n%q", got)
	}
}

// --- Constants ------------------------------------------------------------

func TestConstants_MatchPython(t *testing.T) {
	if MaxInlineAttachmentChars != 24000 {
		t.Errorf("MaxInlineAttachmentChars = %d, want 24000", MaxInlineAttachmentChars)
	}
	if MinInlineAttachmentSlice != 500 {
		t.Errorf("MinInlineAttachmentSlice = %d, want 500", MinInlineAttachmentSlice)
	}
	if PDFContentMarker != "\n\n[PDF content]:" {
		t.Errorf("PDFContentMarker = %q, want %q", PDFContentMarker, "\n\n[PDF content]:")
	}
}

// --- humanInt -------------------------------------------------------------

func TestHumanInt(t *testing.T) {
	cases := []struct {
		in   int64
		want string
	}{
		{0, "0"},
		{1, "1"},
		{999, "999"},
		{1000, "1,000"},
		{12345, "12,345"},
		{1000000, "1,000,000"},
		{1234567, "1,234,567"},
		{-42, "-42"},
	}
	for _, tc := range cases {
		if got := humanInt(tc.in); got != tc.want {
			t.Errorf("humanInt(%d) = %q, want %q", tc.in, got, tc.want)
		}
	}
}
