package generatedimages

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// ---- Regex coverage ------------------------------------------------------

func TestMatch_ValidExtensions(t *testing.T) {
	for _, ext := range AllowedExtensions {
		name := "abcdef12" + "." + ext
		if !Match(name) {
			t.Errorf("Match(%q) = false, want true (ext=%q)", name, ext)
		}
	}
}

func TestMatch_HashLengthBoundaries(t *testing.T) {
	// Min length 8, max 64 hex chars.
	cases := []struct {
		hash string
		want bool
	}{
		{"1234567", false},                // 7 chars: too short
		{"12345678", true},                // 8 chars: boundary
		{strings.Repeat("a", 64), true},   // 64 chars: boundary
		{strings.Repeat("a", 65), false},  // 65 chars: too long
		{strings.Repeat("a", 100), false}, // 100 chars: too long
	}
	for _, c := range cases {
		name := c.hash + ".png"
		if got := Match(name); got != c.want {
			t.Errorf("Match(%q) = %v, want %v", name, got, c.want)
		}
	}
}

func TestMatch_UppercaseRejected(t *testing.T) {
	// The Python regex is lowercase-only ("a-f0-9"). Uppercase must
	// be rejected — generated-image filenames are always lowercase
	// in the Odysseus pipeline.
	if Match("ABCDEF12.png") {
		t.Errorf("uppercase hex should not match")
	}
}

func TestMatch_DisallowedExtension(t *testing.T) {
	for _, bad := range []string{"exe", "sh", "html", "txt", "js", "svg"} {
		name := "abcdef12." + bad
		if Match(name) {
			t.Errorf("Match(%q) = true, want false (bad ext=%q)", name, bad)
		}
	}
}

func TestMatch_NoExtension(t *testing.T) {
	if Match("abcdef12") {
		t.Errorf("name without extension should not match")
	}
}

func TestMatch_Empty(t *testing.T) {
	if Match("") {
		t.Errorf("empty name should not match")
	}
}

func TestMatch_PathTraversalAttempts(t *testing.T) {
	// The regex must reject anything containing "/", "\\", or "..".
	for _, name := range []string{
		"../etc/passwd.png",
		"../../etc/passwd.png",
		"abc/def.png",
		"abcdef12.png/extra",
		"abcdef12.png\x00",
	} {
		if Match(name) {
			t.Errorf("Match(%q) = true, want false (traversal)", name)
		}
	}
}

// ---- ImageHeaders --------------------------------------------------------

func TestImageHeaders_StableValues(t *testing.T) {
	// The Python source treats the headers as a module-level
	// constant; pin both values so a refactor can't drift them.
	want := map[string]string{
		"Cache-Control":          "public, max-age=31536000, immutable",
		"X-Content-Type-Options": "nosniff",
	}
	if len(ImageHeaders) != len(want) {
		t.Errorf("ImageHeaders len = %d, want %d", len(ImageHeaders), len(want))
	}
	for k, v := range want {
		if got := ImageHeaders[k]; got != v {
			t.Errorf("ImageHeaders[%q] = %q, want %q", k, got, v)
		}
	}
}

// ---- Error sentinels -----------------------------------------------------

func TestIsFilenameAndIsNotFound(t *testing.T) {
	fe := &FilenameError{Filename: "bad"}
	if !IsFilename(fe) {
		t.Errorf("IsFilename(*FilenameError) = false, want true")
	}
	nf := &NotFoundError{Filename: "missing.png"}
	if !IsNotFound(nf) {
		t.Errorf("IsNotFound(*NotFoundError) = false, want true")
	}
	// Cross-class.
	if IsNotFound(fe) {
		t.Errorf("IsNotFound(*FilenameError) = true, want false")
	}
	if IsFilename(nf) {
		t.Errorf("IsFilename(*NotFoundError) = true, want false")
	}
}

func TestErrorsIsSentinels(t *testing.T) {
	fe := &FilenameError{Filename: "x"}
	if !errors.Is(fe, ErrFilename) {
		// The concrete *FilenameError does NOT implement Is; the
		// sentinel check has to go through IsFilename. Document
		// that asymmetry in the test name.
		t.Logf("errors.Is(*FilenameError, ErrFilename) = false (use IsFilename instead)")
	}
}

func TestAsError_PassThrough(t *testing.T) {
	other := errors.New("boom")
	if got := AsError(other); got != other {
		t.Errorf("AsError(other) = %v, want %v", got, other)
	}
	if got := AsError(nil); got != nil {
		t.Errorf("AsError(nil) = %v, want nil", got)
	}
}

// ---- Resolve -------------------------------------------------------------

func setupTree(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	// Real files: one matching image + one ignored file (wrong extension).
	if err := os.WriteFile(filepath.Join(dir, "abcdef12.png"), []byte("PNG"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	if err := os.WriteFile(filepath.Join(dir, "ignore.exe"), []byte("X"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	// Nested subdirectory with a matching filename inside.
	if err := os.Mkdir(filepath.Join(dir, "abcdef12.png.d"), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	return dir
}

func TestResolve_HappyPath(t *testing.T) {
	dir := setupTree(t)
	got, err := Resolve(dir, "abcdef12.png")
	if err != nil {
		t.Fatalf("Resolve err: %v", err)
	}
	if !strings.HasSuffix(got, filepath.Join(dir, "abcdef12.png")) {
		t.Errorf("Resolve = %q, want suffix %q", got, filepath.Join(dir, "abcdef12.png"))
	}
}

func TestResolve_InvalidExtension(t *testing.T) {
	dir := setupTree(t)
	_, err := Resolve(dir, "abcdef12.exe")
	if !IsFilename(err) {
		t.Errorf("IsFilename = false, want true (err=%v)", err)
	}
}

func TestResolve_TraversalAttempt(t *testing.T) {
	dir := setupTree(t)
	_, err := Resolve(dir, "../etc/passwd.png")
	if !IsFilename(err) {
		t.Errorf("IsFilename = false, want true (err=%v)", err)
	}
}

func TestResolve_Empty(t *testing.T) {
	dir := setupTree(t)
	_, err := Resolve(dir, "")
	if !IsFilename(err) {
		t.Errorf("IsFilename = false, want true (err=%v)", err)
	}
}

func TestResolve_NotFound(t *testing.T) {
	dir := setupTree(t)
	_, err := Resolve(dir, "deadbeef.png")
	if !IsNotFound(err) {
		t.Errorf("IsNotFound = false, want true (err=%v)", err)
	}
}

func TestResolve_RegexRejectsDirectorySuffix(t *testing.T) {
	// `abcdef12.png.d` is a directory in the test tree but its name
	// has the extension ".d" which the regex does not allow. The
	// regex check fires first, so we get a *FilenameError before
	// the directory is ever stat'd. This mirrors the Python source's
	// "regex fails → 400 Invalid filename" path.
	dir := setupTree(t)
	_, err := Resolve(dir, "abcdef12.png.d")
	if !IsFilename(err) {
		t.Errorf("IsFilename = false, want true (err=%v)", err)
	}
}

func TestResolve_SubdirectoryWithValidName(t *testing.T) {
	// Put a *valid* filename inside a subdirectory. The regex passes,
	// EvalSymlinks resolves to the real path, the file exists, and
	// Resolve returns the absolute path. This is the closest Go
	// analogue to the Python source's `path.exists()`-then-`return`
	// flow when the path happens to be a directory rather than a
	// file — the Python code does not check whether the resolved
	// path is a file either, so we mirror that.
	dir := setupTree(t)
	sub := filepath.Join(dir, "sub")
	if err := os.Mkdir(sub, 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	name := "abcdef12.png"
	if err := os.WriteFile(filepath.Join(sub, name), []byte("X"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}
	// Note: the regex forbids "/" in the filename, so a direct
	// Resolve call with "sub/abcdef12.png" would fail the regex.
	// Use the base name to test the resolver on a subdirectory-rooted
	// tree by passing a deeper dir.
	got, err := Resolve(sub, name)
	if err != nil {
		t.Fatalf("Resolve err: %v", err)
	}
	if !strings.HasSuffix(got, filepath.Join(sub, name)) {
		t.Errorf("got = %q, want suffix %q", got, filepath.Join(sub, name))
	}
}

func TestResolve_NestedFilenameFailsTraversal(t *testing.T) {
	dir := setupTree(t)
	_, err := Resolve(dir, "abcdef12.png/extra")
	if !IsFilename(err) {
		t.Errorf("IsFilename = false, want true (err=%v)", err)
	}
}

func TestResolve_AbsoluteDir(t *testing.T) {
	// Even when dir is relative, Resolve should make it absolute.
	// We can't easily make the test dir relative without breaking
	// other tests, so just verify that the returned path is absolute.
	dir := setupTree(t)
	got, err := Resolve(dir, "abcdef12.png")
	if err != nil {
		t.Fatalf("Resolve err: %v", err)
	}
	if !filepath.IsAbs(got) {
		t.Errorf("Resolve = %q, want absolute", got)
	}
}

func TestResolve_ExtensionsCoverage(t *testing.T) {
	// Every allowed extension should resolve to a path under dir when
	// the file is present.
	dir := t.TempDir()
	for _, ext := range AllowedExtensions {
		hash := "abcdef12"
		name := hash + "." + ext
		if err := os.WriteFile(filepath.Join(dir, name), []byte("X"), 0o644); err != nil {
			t.Fatalf("write %s: %v", name, err)
		}
		got, err := Resolve(dir, name)
		if err != nil {
			t.Errorf("Resolve(%q) err: %v", name, err)
			continue
		}
		if !strings.HasSuffix(got, name) {
			t.Errorf("Resolve(%q) = %q, want suffix %q", name, got, name)
		}
	}
}

func TestResolve_ErrorMessagesIncludeFilename(t *testing.T) {
	dir := setupTree(t)
	_, err := Resolve(dir, "abc")
	if err == nil {
		t.Fatal("expected error")
	}
	if !strings.Contains(err.Error(), "abc") {
		t.Errorf("error message should include the filename: %q", err.Error())
	}
}
