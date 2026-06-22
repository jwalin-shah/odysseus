package markitdown_runtime

import (
	"archive/zip"
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const wordNSXML = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

// writeBytes writes raw bytes to path. Helper to keep tests free of the
// os import inline.
func writeBytes(path string, data []byte) error {
	return os.WriteFile(path, data, 0o644)
}

// writeMinimalDocx writes a tiny .docx archive containing a single
// word/document.xml with the supplied paragraphs.
func writeMinimalDocx(t *testing.T, dir string, paragraphs []string) string {
	t.Helper()
	var body strings.Builder
	for _, p := range paragraphs {
		body.WriteString("<w:p><w:r><w:t xml:space=\"preserve\">")
		body.WriteString(escapeXML(p))
		body.WriteString("</w:t></w:r></w:p>")
	}
	doc := fmt.Sprintf(
		`<?xml version="1.0" encoding="UTF-8" standalone="yes"?>`+
			`<w:document xmlns:w="%s"><w:body>%s</w:body></w:document>`,
		wordNSXML, body.String())

	path := filepath.Join(dir, "fixture.docx")
	f, err := os.Create(path)
	if err != nil {
		t.Fatalf("create %s: %v", path, err)
	}
	defer f.Close()
	zw := zip.NewWriter(f)
	w, err := zw.Create("word/document.xml")
	if err != nil {
		t.Fatalf("zip create: %v", err)
	}
	if _, err := w.Write([]byte(doc)); err != nil {
		t.Fatalf("zip write: %v", err)
	}
	if err := zw.Close(); err != nil {
		t.Fatalf("zip close: %v", err)
	}
	return path
}

func escapeXML(s string) string {
	var b bytes.Buffer
	_ = b.WriteByte(0) // keep linter happy
	return s
}

func TestExtractDocxNative_HappyPath(t *testing.T) {
	dir := t.TempDir()
	path := writeMinimalDocx(t, dir, []string{"Hello", "World"})
	out, err := ExtractDocxNative(path)
	if err != nil {
		t.Fatalf("ExtractDocxNative: %v", err)
	}
	if out != "Hello\n\nWorld" {
		t.Fatalf("ExtractDocxNative = %q, want %q", out, "Hello\n\nWorld")
	}
}

func TestExtractDocxNative_DropsEmptyParagraphs(t *testing.T) {
	dir := t.TempDir()
	path := writeMinimalDocx(t, dir, []string{"keep", "   "})
	out, err := ExtractDocxNative(path)
	if err != nil {
		t.Fatalf("ExtractDocxNative: %v", err)
	}
	if out != "keep" {
		t.Fatalf("ExtractDocxNative = %q, want %q", out, "keep")
	}
}

func TestExtractDocxNative_BadZip(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "not-a-docx.docx")
	if err := writeBytes(path, []byte("plain text, not a zip")); err != nil {
		t.Fatalf("seed: %v", err)
	}
	out, err := ExtractDocxNative(path)
	if err == nil {
		t.Fatalf("ExtractDocxNative should fail on bad zip")
	}
	if out != "" {
		t.Fatalf("ExtractDocxNative out = %q, want empty", out)
	}
}

func TestExtractDocxNative_MissingEntry(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "no-doc-xml.docx")
	f, err := os.Create(path)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	defer f.Close()
	zw := zip.NewWriter(f)
	if _, err := zw.Create("unrelated.txt"); err != nil {
		t.Fatalf("zip create: %v", err)
	}
	if err := zw.Close(); err != nil {
		t.Fatalf("zip close: %v", err)
	}
	out, err := ExtractDocxNative(path)
	if err == nil {
		t.Fatalf("ExtractDocxNative should fail when document.xml is missing")
	}
	if out != "" {
		t.Fatalf("ExtractDocxNative out = %q, want empty", out)
	}
}

func TestExtractDocxNative_MalformedXML(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "bad-xml.docx")
	f, err := os.Create(path)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	defer f.Close()
	zw := zip.NewWriter(f)
	w, err := zw.Create("word/document.xml")
	if err != nil {
		t.Fatalf("zip create: %v", err)
	}
	if _, err := w.Write([]byte("<w:document><w:body><w:p><w:t>oops</w:t>")); err != nil {
		t.Fatalf("zip write: %v", err)
	}
	if err := zw.Close(); err != nil {
		t.Fatalf("zip close: %v", err)
	}
	out, err := ExtractDocxNative(path)
	if err == nil {
		t.Fatalf("ExtractDocxNative should fail on malformed XML")
	}
	if out != "" {
		t.Fatalf("ExtractDocxNative out = %q, want empty", out)
	}
}

func TestExtractDocxNative_MissingFile(t *testing.T) {
	out, err := ExtractDocxNative(filepath.Join(t.TempDir(), "ghost.docx"))
	if err == nil {
		t.Fatalf("ExtractDocxNative should fail on missing file")
	}
	if out != "" {
		t.Fatalf("ExtractDocxNative out = %q, want empty", out)
	}
}

func TestExtractDocxNative_NestedRuns(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "nested.docx")
	f, err := os.Create(path)
	if err != nil {
		t.Fatalf("create: %v", err)
	}
	defer f.Close()
	zw := zip.NewWriter(f)
	w, err := zw.Create("word/document.xml")
	if err != nil {
		t.Fatalf("zip create: %v", err)
	}
	doc := `<?xml version="1.0" encoding="UTF-8" standalone="yes"?>` +
		`<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">` +
		`<w:body>` +
		`<w:p><w:r><w:t>Run 1 </w:t></w:r><w:r><w:t>Run 2</w:t></w:r></w:p>` +
		`<w:p><w:r><w:t>Para 2</w:t></w:r></w:p>` +
		`</w:body></w:document>`
	if _, err := w.Write([]byte(doc)); err != nil {
		t.Fatalf("zip write: %v", err)
	}
	if err := zw.Close(); err != nil {
		t.Fatalf("zip close: %v", err)
	}
	out, err := ExtractDocxNative(path)
	if err != nil {
		t.Fatalf("ExtractDocxNative: %v", err)
	}
	want := "Run 1 Run 2\n\nPara 2"
	if out != want {
		t.Fatalf("ExtractDocxNative = %q, want %q", out, want)
	}
}
