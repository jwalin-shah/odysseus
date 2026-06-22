// Package pdfruntime is the Go port of src/pdf_runtime.py. The Python source
// is a thin loader around the optional PyMuPDF dependency, used by the PDF
// viewer feature:
//
//	PDF_VIEWER_PYMUPDF_MISSING = (
//	    "PDF viewer requires PyMuPDF. Install optional PDF dependencies with "
//	    "`pip install -r requirements-optional.txt` (PyMuPDF is AGPL-3.0)."
//	)
//
//	def load_pymupdf_for_pdf_viewer():
//	    try:
//	        import fitz
//	    except ImportError as exc:
//	        raise RuntimeError(PDF_VIEWER_PYMUPDF_MISSING) from exc
//	    return fitz
//
// PyMuPDF is an AGPL-3.0 native module that is intentionally not linked
// into the main Go binary. The Go port exposes the same "lazy import +
// user-facing setup hint" contract through Loader and the package-level
// MissingMessage / ErrMissing sentinels.
//
// Callers wire their PDF viewer behind a Loader:
//
//	var load pdfruntime.Loader = pdfruntime.FuncLoader(func() (any, error) {
//	    return pymupdf.Open(path)
//	})
//	mod, err := load.Load()
//	if errors.Is(err, pdfruntime.ErrMissing) {
//	    return http.StatusFailedDependency, pdfruntime.MissingMessage
//	}
package pdfruntime

import "errors"

// MissingMessage is the user-facing setup hint surfaced when the optional
// PyMuPDF dependency is not present. Mirrors
// PDF_VIEWER_PYMUPDF_MISSING in src/pdf_runtime.py.
//
// It is intentionally a constant (not a fmt.Sprintf template) because the
// Python source ships it as a static string. Operators and CI scripts can
// grep for it in logs.
const MissingMessage = "PDF viewer requires PyMuPDF. Install optional PDF dependencies with `pip install -r requirements-optional.txt` (PyMuPDF is AGPL-3.0)."

// ErrMissing is the sentinel returned by Loader implementations when the
// underlying dependency (PyMuPDF / fitz) is not installed. Callers should
// match with errors.Is(err, pdfruntime.ErrMissing) and respond with
// MissingMessage as the user-facing body.
//
// Mirrors the `raise RuntimeError(PDF_VIEWER_PYMUPDF_MISSING) from exc`
// path in src/pdf_runtime.py: in Go we surface it as a sentinel error
// instead of a string match on the error message.
var ErrMissing = errors.New("pymupdf missing")

// Loader abstracts the optional dependency boundary. The zero value is
// not usable; callers should construct one with FuncLoader or supply a
// custom implementation (typically backed by a build-tag-gated file that
// calls into PyMuPDF via cgo).
//
// The Load method returns the resolved module/handle on success. On
// failure it should return ErrMissing (or an error wrapping it) so
// callers can branch with errors.Is without inspecting strings.
type Loader interface {
	Load() (any, error)
}

// LoaderFunc is the function-form adapter for Loader. Mirrors the
// pattern used in src/endpoint_resolver.py where the actual loader is
// swapped in tests.
type LoaderFunc func() (any, error)

// Load implements Loader.
func (f LoaderFunc) Load() (any, error) { return f() }

// FuncLoader wraps a closure as a Loader. Provided for parity with
// `pdfruntime.FuncLoader(func() ...)`-style APIs in other Go ports in
// this repo (e.g. urlsecurity's helpers).
func FuncLoader(fn func() (any, error)) Loader { return LoaderFunc(fn) }

// MissingError constructs an error wrapping ErrMissing with MissingMessage
// as the user-facing message. Equivalent to Python's
// `raise RuntimeError(PDF_VIEWER_PYMUPDF_MISSING) from exc` — the
// underlying cause is preserved via %w so errors.Is(err, ErrMissing)
// still matches.
//
// Callers that already have a sentinel-loaded cause (e.g. an ImportError
// equivalent from the underlying loader) should pass it as cause; nil is
// acceptable when there is no underlying error to wrap.
func MissingError(cause error) error {
	if cause == nil {
		return &missingError{}
	}
	return &missingError{cause: cause}
}

// missingError is the concrete error type returned by MissingError. It
// implements errors.Is(err, ErrMissing) and Unwrap() so the underlying
// cause is still reachable.
type missingError struct{ cause error }

func (e *missingError) Error() string { return MissingMessage }
func (e *missingError) Is(target error) bool {
	return target == ErrMissing
}
func (e *missingError) Unwrap() error { return e.cause }

// StaticLoader is a Loader that always succeeds with the supplied value.
// Useful in tests and in the demo CLI where we want to exercise the
// happy path without requiring PyMuPDF.
type StaticLoader struct {
	Value any
}

// Load implements Loader.
func (s StaticLoader) Load() (any, error) { return s.Value, nil }

// FailingLoader is a Loader that always returns MissingError. Useful in
// tests that exercise the user-facing setup-hint path.
type FailingLoader struct{}

// Load implements Loader.
func (FailingLoader) Load() (any, error) { return nil, MissingError(nil) }
