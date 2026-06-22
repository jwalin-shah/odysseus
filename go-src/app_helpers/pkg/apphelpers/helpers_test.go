package apphelpers

import (
	"encoding/base64"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// ---- ReadIfExists --------------------------------------------------------

func TestReadIfExists_MissingReturnsEmpty(t *testing.T) {
	missing := filepath.Join(t.TempDir(), "nope.txt")
	if got := ReadIfExists(missing); got != "" {
		t.Errorf("ReadIfExists(missing) = %q, want \"\"", got)
	}
}

func TestReadIfExists_EmptyPathReturnsEmpty(t *testing.T) {
	if got := ReadIfExists(""); got != "" {
		t.Errorf("ReadIfExists(\"\") = %q, want \"\"", got)
	}
}

func TestReadIfExists_StripsTrailingWhitespace(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "x.txt")
	if err := os.WriteFile(p, []byte("  hello world\n\n"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	if got := ReadIfExists(p); got != "hello world" {
		t.Errorf("ReadIfExists = %q, want %q", got, "hello world")
	}
}

func TestReadIfExists_DirectoryReturnsEmpty(t *testing.T) {
	// os.ReadFile on a directory returns an error on most platforms;
	// we want ReadIfExists to silently return "" rather than bubble
	// the I/O error up.
	dir := t.TempDir()
	if got := ReadIfExists(dir); got != "" {
		t.Errorf("ReadIfExists(directory) = %q, want \"\"", got)
	}
}

// ---- FileToDataURL -------------------------------------------------------

func TestFileToDataURL_RoundTrip(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "hello.txt")
	want := "hello, world"
	if err := os.WriteFile(p, []byte(want), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	got, err := FileToDataURL(p, "text/plain")
	if err != nil {
		t.Fatalf("FileToDataURL err: %v", err)
	}
	if !strings.HasPrefix(got, "data:text/plain;base64,") {
		t.Errorf("prefix wrong: %q", got)
	}
	// Decode the payload and confirm it round-trips.
	payload := strings.TrimPrefix(got, "data:text/plain;base64,")
	decoded, err := base64.StdEncoding.DecodeString(payload)
	if err != nil {
		t.Fatalf("decode: %v", err)
	}
	if string(decoded) != want {
		t.Errorf("decoded = %q, want %q", decoded, want)
	}
}

func TestFileToDataURL_EmptyPath(t *testing.T) {
	if _, err := FileToDataURL("", "text/plain"); err == nil {
		t.Errorf("expected error for empty path")
	}
}

func TestFileToDataURL_EmptyMime(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "x")
	if err := os.WriteFile(p, []byte("x"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	if _, err := FileToDataURL(p, ""); err == nil {
		t.Errorf("expected error for empty mime")
	}
}

func TestFileToDataURL_MissingFile(t *testing.T) {
	if _, err := FileToDataURL(filepath.Join(t.TempDir(), "missing"), "text/plain"); err == nil {
		t.Errorf("expected error for missing file")
	}
}

// ---- AbsJoin -------------------------------------------------------------

func TestAbsJoin_AbsoluteBase(t *testing.T) {
	got := AbsJoin("/base/dir", "sub/file.txt")
	want := "/base/dir/sub/file.txt"
	if got != want {
		t.Errorf("AbsJoin = %q, want %q", got, want)
	}
}

func TestAbsJoin_RelativeBase(t *testing.T) {
	got := AbsJoin("relative/dir", "x")
	if !filepath.IsAbs(got) {
		t.Errorf("AbsJoin = %q, want absolute", got)
	}
	if !strings.HasSuffix(got, filepath.Join("relative", "dir", "x")) {
		t.Errorf("AbsJoin = %q, want suffix %q", got, filepath.Join("relative", "dir", "x"))
	}
}

func TestAbsJoin_RelTraversalEscapes(t *testing.T) {
	// AbsJoin does not guard against traversal — that's
	// InsideBaseDir's job — but the cleaned path should reflect the
	// textual normalization.
	got := AbsJoin("/base", "../escape")
	if got != "/escape" {
		t.Errorf("AbsJoin = %q, want /escape", got)
	}
}

func TestAbsJoin_EmptyRel(t *testing.T) {
	got := AbsJoin("/base", "")
	if got != "/base" {
		t.Errorf("AbsJoin = %q, want /base", got)
	}
}

// ---- InsideBaseDir -------------------------------------------------------

func TestInsideBaseDir_Inside(t *testing.T) {
	base := t.TempDir()
	sub := filepath.Join(base, "sub")
	if err := os.Mkdir(sub, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if !InsideBaseDir(base, sub) {
		t.Errorf("expected sub to be inside base")
	}
}

func TestInsideBaseDir_BaseItself(t *testing.T) {
	base := t.TempDir()
	if !InsideBaseDir(base, base) {
		t.Errorf("expected base to be inside itself")
	}
}

func TestInsideBaseDir_Outside(t *testing.T) {
	base := t.TempDir()
	outside := t.TempDir()
	if InsideBaseDir(base, outside) {
		t.Errorf("expected outside NOT to be inside base")
	}
}

func TestInsideBaseDir_EmptyArgs(t *testing.T) {
	base := t.TempDir()
	if InsideBaseDir("", base) {
		t.Errorf("empty base should be false")
	}
	if InsideBaseDir(base, "") {
		t.Errorf("empty path should be false")
	}
}

func TestInsideBaseDir_TraversalSibling(t *testing.T) {
	// base = /tmp/x/, path = /tmp/x/../y — must resolve to /tmp/y
	// which is OUTSIDE /tmp/x after symlink resolution.
	base := t.TempDir()
	parent := filepath.Dir(base)
	outside := filepath.Join(parent, "sibling-outside")
	if err := os.Mkdir(outside, 0o755); err != nil {
		t.Fatalf("mkdir outside: %v", err)
	}
	if InsideBaseDir(base, outside) {
		t.Errorf("sibling dir should NOT be inside base")
	}
}

func TestInsideBaseDir_NestedDeep(t *testing.T) {
	base := t.TempDir()
	deep := filepath.Join(base, "a", "b", "c", "d")
	if err := os.MkdirAll(deep, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if !InsideBaseDir(base, deep) {
		t.Errorf("deep nested path should be inside base")
	}
}

func TestInsideBaseDir_MissingPath(t *testing.T) {
	// path doesn't exist — EvalSymlinks fails, so the function must
	// return false (not panic).
	base := t.TempDir()
	missing := filepath.Join(base, "nope")
	if InsideBaseDir(base, missing) {
		t.Errorf("missing path should NOT be inside base")
	}
}

func TestInsideBaseDir_SymlinkInside(t *testing.T) {
	// Symlink that points inside base: must be reported as inside.
	base := t.TempDir()
	target := filepath.Join(base, "real")
	if err := os.Mkdir(target, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	linkDir := t.TempDir()
	link := filepath.Join(linkDir, "link")
	if err := os.Symlink(target, link); err != nil {
		t.Skipf("symlink not supported: %v", err)
	}
	if !InsideBaseDir(base, link) {
		t.Errorf("symlink inside base should resolve to inside")
	}
}

func TestInsideBaseDir_SymlinkOutside(t *testing.T) {
	// Symlink that escapes base: must be reported as outside.
	base := t.TempDir()
	outside := t.TempDir()
	linkDir := t.TempDir()
	link := filepath.Join(linkDir, "escape")
	if err := os.Symlink(outside, link); err != nil {
		t.Skipf("symlink not supported: %v", err)
	}
	if InsideBaseDir(base, link) {
		t.Errorf("symlink outside base should resolve to outside")
	}
}
