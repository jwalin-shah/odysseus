package markitdown_runtime

import (
	"errors"
	"path/filepath"
	"sort"
	"strings"
	"testing"
)

func TestIsMarkitdownFormat(t *testing.T) {
	cases := []struct {
		path string
		want bool
	}{
		{"foo.docx", true},
		{"foo.DOCX", true},
		{"foo.pptx", true},
		{"foo.xlsx", true},
		{"foo.xls", true},
		{"foo.epub", true},
		{"foo.txt", false},
		{"foo", false},
		{"foo.tar.docx", true},
		{"", false},
		{"/abs/path/notes.PDF", false},
	}
	for _, c := range cases {
		t.Run(c.path, func(t *testing.T) {
			if got := IsMarkitdownFormat(c.path); got != c.want {
				t.Fatalf("IsMarkitdownFormat(%q) = %v, want %v", c.path, got, c.want)
			}
		})
	}
}

func TestMarkitdownExtsExactSet(t *testing.T) {
	want := []string{".docx", ".epub", ".pptx", ".xls", ".xlsx"}
	got := append([]string{}, MARKITDOWN_EXTS...)
	sort.Strings(got)
	if strings.Join(got, ",") != strings.Join(want, ",") {
		t.Fatalf("MARKITDOWN_EXTS = %v, want %v", MARKITDOWN_EXTS, want)
	}
}

func TestMarkitdownMissingConstant(t *testing.T) {
	if !strings.Contains(MARKITDOWN_MISSING, "markitdown") {
		t.Fatalf("MARKITDOWN_MISSING should mention markitdown: %q", MARKITDOWN_MISSING)
	}
	if !strings.Contains(MARKITDOWN_MISSING, "pip install") {
		t.Fatalf("MARKITDOWN_MISSING should mention install command: %q", MARKITDOWN_MISSING)
	}
	if MARKITDOWN_MISSING != ErrMarkItDownMissing.Error() {
		t.Fatalf("ErrMarkItDownMissing should wrap MARKITDOWN_MISSING: got %q want %q",
			ErrMarkItDownMissing.Error(), MARKITDOWN_MISSING)
	}
}

func TestLoadMarkItDownMissing(t *testing.T) {
	conv, err := LoadMarkItDown()
	if conv != nil {
		t.Fatalf("LoadMarkItDown should return a nil converter when missing")
	}
	if !errors.Is(err, ErrMarkItDownMissing) {
		t.Fatalf("LoadMarkItDown err = %v, want ErrMarkItDownMissing", err)
	}
}

func TestConvertFallsBackForDocx(t *testing.T) {
	dir := t.TempDir()
	path := writeMinimalDocx(t, dir, []string{"Hello world", "Second paragraph"})

	out, err := Convert(path)
	if err != nil {
		t.Fatalf("Convert err: %v", err)
	}
	if !strings.Contains(out, "Hello world") || !strings.Contains(out, "Second paragraph") {
		t.Fatalf("Convert output missing paragraphs: %q", out)
	}
	if !strings.Contains(out, "\n\n") {
		t.Fatalf("Convert output should join paragraphs with blank line, got %q", out)
	}
}

func TestConvertMissingLogsAndReturnsEmpty(t *testing.T) {
	dir := t.TempDir()
	pptx := filepath.Join(dir, "deck.pptx")
	if err := writeBytes(pptx, []byte("not a real pptx")); err != nil {
		t.Fatalf("seed: %v", err)
	}
	out, err := Convert(pptx)
	if err != nil {
		t.Fatalf("Convert err: %v", err)
	}
	if out != "" {
		t.Fatalf("Convert output = %q, want empty", out)
	}
}

func TestConvertNonExistentDocx(t *testing.T) {
	out, err := Convert(filepath.Join(t.TempDir(), "missing.docx"))
	if err != nil {
		t.Fatalf("Convert err: %v", err)
	}
	if out != "" {
		t.Fatalf("Convert output = %q, want empty", out)
	}
}

func TestConvertNonStringEmpty(t *testing.T) {
	// Mirrors the Python is_markitdown_format guard: a non-string/empty
	// path skips the docx branch and returns empty.
	out, err := Convert("")
	if err != nil {
		t.Fatalf("Convert err: %v", err)
	}
	if out != "" {
		t.Fatalf("Convert(\"\") = %q, want empty", out)
	}
}
