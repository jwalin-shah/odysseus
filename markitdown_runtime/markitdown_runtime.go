// Package markitdown_runtime is a Go port of src/markitdown_runtime.py. It
// exposes a tiny façade for converting Office/EPUB documents to Markdown
// text, with a graceful fallback to a pure-Go .docx extractor when the
// optional markitdown dependency is unavailable.
//
// The package does not depend on any third-party library. It models the
// Python module's surface (IsMarkitdownFormat, LoadMarkItDown, Convert) on
// top of stdlib archive/zip + encoding/xml.
package markitdown_runtime

import (
	"errors"
	"log"
	"path/filepath"
	"strings"
)

// MARKITDOWN_MISSING is the user-facing setup hint surfaced when markitdown
// is not installed. It mirrors the Python constant of the same name so the
// two runtimes can share the same downstream messaging.
const MARKITDOWN_MISSING = "Office/EPUB document extraction requires markitdown. Install optional " +
	"dependencies with `pip install -r requirements-optional.txt`."

// ErrMarkItDownMissing is the sentinel returned by LoadMarkItDown when the
// optional markitdown dependency is not importable. Callers can use
// errors.Is to branch on it (analogous to the Python `except RuntimeError`).
var ErrMarkItDownMissing = errors.New(MARKITDOWN_MISSING)

// MARKITDOWN_EXTS lists the file extensions routed through markitdown.
// Mirrors src/markitdown_runtime.MARKITDOWN_EXTS exactly.
var MARKITDOWN_EXTS = []string{".docx", ".pptx", ".xlsx", ".xls", ".epub"}

// IsMarkitdownFormat reports whether path's extension is one we route through
// markitdown. The check is case-insensitive on the suffix and matches the
// Python implementation's `os.path.splitext(path)[1].lower()` semantics.
func IsMarkitdownFormat(path string) bool {
	if path == "" {
		return false
	}
	ext := strings.ToLower(filepath.Ext(path))
	for _, candidate := range MARKITDOWN_EXTS {
		if ext == candidate {
			return true
		}
	}
	return false
}

// LoadMarkItDown returns a converter function that wraps the markitdown
// dependency. When markitdown is not installed the function returns
// ErrMarkItDownMissing so callers can degrade gracefully. The Go port does
// not bundle a CGo markitdown shim — the optional dependency is treated as
// absent — so the fallback path is the common case here.
func LoadMarkItDown() (func(path string) (string, error), error) {
	// The Python module does `from markitdown import MarkItDown`. We have no
	// native binding in this Go port, so we surface the same sentinel error
	// callers would see in a fresh Python environment.
	return nil, ErrMarkItDownMissing
}

// Convert runs the document-to-markdown pipeline for path.
//
// The return semantics mirror the Python `convert_to_markdown`:
//   - markitdown unavailable + path is a .docx: returns the native
//     extractor's output (or empty string + nil error if extraction also
//     fails) and logs a warning. Mirrors the Python info-log path.
//   - markitdown unavailable + path is not a .docx: returns empty string +
//     nil error and logs a warning.
//   - markitdown conversion errored: returns empty string + nil error and
//     logs a warning.
//   - markitdown conversion succeeded: returns the extracted Markdown text
//     and a nil error.
func Convert(path string) (string, error) {
	converter, err := LoadMarkItDown()
	if err != nil {
		if errors.Is(err, ErrMarkItDownMissing) && strings.EqualFold(filepath.Ext(path), ".docx") {
			text, nativeErr := ExtractDocxNative(path)
			if nativeErr != nil {
				log.Printf("markitdown not installed; native .docx extractor failed for %s: %v", path, nativeErr)
				return "", nil
			}
			if text != "" {
				log.Printf("markitdown not installed — used native .docx extractor for %s", path)
			}
			return text, nil
		}
		log.Printf("markitdown not installed; cannot extract %s", path)
		return "", nil
	}
	out, err := converter(path)
	if err != nil {
		log.Printf("markitdown failed to convert %s: %v", path, err)
		return "", nil
	}
	return out, nil
}
