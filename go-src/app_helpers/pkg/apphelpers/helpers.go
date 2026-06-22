// Package apphelpers is the Go port of src/app_helpers.py. The Python
// module exposes four tiny helpers used by various routes and services:
//
//	read_if_exists(path)              -> "" if the file is missing or unreadable
//	file_to_data_url(path, mime)      -> "data:<mime>;base64,<...>"
//	abs_join(base_dir, rel)           -> absolute path joined to rel
//	inside_base_dir(base_dir, path)   -> True iff path is inside base_dir
//
// The Go port keeps all four contracts. The two filesystem helpers
// (ReadIfExists, FileToDataURL) use the same defensive read pattern
// the Python source uses: a missing or unreadable file is not an
// error, it returns the zero value.
//
// inside_base_dir is the path-traversal guard every consumer of
// user-supplied filenames needs. We re-implement it in terms of
// filepath.EvalSymlinks + filepath.Rel so symlink games cannot smuggle
// a path out of base_dir — the Python version uses os.path.realpath +
// os.path.commonpath for the same reason.
package apphelpers

import (
	"encoding/base64"
	"errors"
	"os"
	"path/filepath"
	"strings"
)

// ReadIfExists returns the trimmed contents of path, or "" if the
// file is missing or unreadable. Mirrors `read_if_exists(path)` in
// src/app_helpers.py.
//
// The trimmed contents are returned as a single string with trailing
// whitespace stripped; the Python source uses f.read().strip() which
// matches strings.TrimSpace. CRLF line endings are preserved inside
// the file; only the trailing whitespace is removed.
func ReadIfExists(path string) string {
	if path == "" {
		return ""
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	return strings.TrimSpace(string(data))
}

// FileToDataURL returns a `data:<mime>;base64,<...>` URL built from
// the file at path. Mirrors `file_to_data_url(path, mime)`. The file
// is read in full; callers should not pass user-controlled mime
// strings without validating them — the helper does not sanitize.
//
// Returns ("", error) when path is empty, the file is unreadable, or
// mime is empty (the Python source would happily emit "data:;base64,..."
// but the Go port refuses empty mime as a footgun guard).
func FileToDataURL(path, mime string) (string, error) {
	if path == "" {
		return "", errors.New("apphelpers: empty path")
	}
	if mime == "" {
		return "", errors.New("apphelpers: empty mime")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	enc := base64.StdEncoding.EncodeToString(data)
	return "data:" + mime + ";base64," + enc, nil
}

// AbsJoin returns filepath.Join(base, rel) with the result converted
// to an absolute, cleaned path. Mirrors `abs_join(base_dir, rel)` in
// the Python source — os.path.abspath(os.path.join(base_dir, rel)).
//
// Note that this does NOT resolve symlinks. Use InsideBaseDir (which
// uses EvalSymlinks) for path-traversal checks; AbsJoin is for
// computing the canonical display path.
func AbsJoin(base, rel string) string {
	joined, err := filepath.Abs(filepath.Join(base, rel))
	if err != nil {
		// filepath.Abs on a non-existent relative path returns the
		// current-dir-prefixed result; the only realistic failure
		// mode here is a malformed rel, in which case we fall back
		// to the joined-cleaned result.
		return filepath.Clean(filepath.Join(base, rel))
	}
	return filepath.Clean(joined)
}

// InsideBaseDir reports whether path resolves (after symlink
// expansion) to a location inside base. Mirrors `inside_base_dir`
// in src/app_helpers.py.
//
// The check uses filepath.EvalSymlinks on both inputs so symlink
// games cannot smuggle a path out of base. When either path cannot be
// resolved (file missing, permission denied), the function returns
// false — callers should treat that as "not inside" rather than
// relying on string comparison.
//
// base and path must both be strings; the Python source guards
// `isinstance(..., str)` and we mirror that by returning false on
// empty inputs.
func InsideBaseDir(base, path string) bool {
	if base == "" || path == "" {
		return false
	}
	baseResolved, err := filepath.EvalSymlinks(base)
	if err != nil {
		return false
	}
	pathResolved, err := filepath.EvalSymlinks(path)
	if err != nil {
		return false
	}
	rel, err := filepath.Rel(baseResolved, pathResolved)
	if err != nil {
		return false
	}
	// filepath.Rel returns a path starting with ".." if path is
	// outside base. We also accept the exact base path (rel == ".")
	// and any descent below it (rel does not start with "..").
	if rel == "." {
		return true
	}
	if rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return false
	}
	return true
}
