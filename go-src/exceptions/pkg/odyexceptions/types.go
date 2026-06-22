// Package odyexceptions provides the Go port of src/exceptions.py. It models
// the Python exception hierarchy as a single Error struct with a Code
// discriminator plus per-class constructors that pre-populate the right
// fields. Callers use errors.Is and errors.As against the package-level
// Err* sentinels the same way they would `raise` and `except` in Python.
package odyexceptions

import "fmt"

// Code is the typed discriminator for the Python exception hierarchy. Each
// Python class maps to a single Code; per-class constructors set it. The
// integer value is informational only — comparisons should always use the
// named constants.
type Code int

const (
	// CodeUnknown is the zero value, used when no class matches. Callers that
	// build an Error with NewError get CodeUnknown until they set it
	// explicitly.
	CodeUnknown Code = iota

	// CodeSessionNotFound mirrors src.exceptions.SessionNotFoundError.
	CodeSessionNotFound

	// CodeInvalidFileUpload mirrors src.exceptions.InvalidFileUploadError.
	CodeInvalidFileUpload

	// CodeLLMService mirrors src.exceptions.LLMServiceError.
	CodeLLMService

	// CodeWebSearch mirrors src.exceptions.WebSearchError.
	CodeWebSearch
)

// String returns the snake-case label that matches the Python class name
// without the "Error" suffix. Used by Error.Error() and the demo CLI.
func (c Code) String() string {
	switch c {
	case CodeSessionNotFound:
		return "session_not_found"
	case CodeInvalidFileUpload:
		return "invalid_file_upload"
	case CodeLLMService:
		return "llm_service"
	case CodeWebSearch:
		return "web_search"
	default:
		return "unknown"
	}
}

// Error is the canonical error type for the port. It wraps a code, a message,
// optional cause, and the per-class structured fields that the Python classes
// carried as instance attributes (session_id, filename, endpoint, query).
//
// The struct satisfies the standard error interface and implements
// errors.Is / errors.As so callers can write:
//
//	if errors.Is(err, odyexceptions.ErrSessionNotFound) { ... }
//	var sfe *odyexceptions.SessionNotFound; if errors.As(err, &sfe) { ... }
type Error struct {
	// Code is the discriminator. Set by the per-class constructors; NewError
	// defaults it to CodeUnknown.
	Code Code

	// Message is the human-readable message — the same string passed to
	// Python's Exception(message) and returned by str(exc).
	Message string

	// Cause is the wrapped underlying error. It can be nil for errors that
	// did not wrap anything (the Python classes don't wrap).
	Cause error

	// SessionID is set by NewSessionNotFound and zero otherwise.
	SessionID string

	// Filename is set by NewInvalidFileUpload and zero otherwise.
	Filename string

	// Endpoint is set by NewLLMService and zero otherwise.
	Endpoint string

	// Query is set by NewWebSearch and zero otherwise.
	Query string
}

// Error renders the wrapped error as a single line. The format mirrors the
// Python str(exc) output: "<code>: <message>". A wrapped Cause is appended with
// ": <cause>" so the chain stays visible in logs.
func (e *Error) Error() string {
	if e == nil {
		return "<nil>"
	}
	base := fmt.Sprintf("%s: %s", e.Code, e.Message)
	if e.Cause != nil {
		base = fmt.Sprintf("%s: %s", base, e.Cause.Error())
	}
	return base
}

// Unwrap exposes the underlying Cause for use with errors.Is / errors.As /
// errors.Unwrap. Returns nil when no cause was set.
func (e *Error) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.Cause
}

// Is matches the receiver against target by class (via the package-level
// Err* sentinels) and, failing that, by Code equality. This lets callers write
// either `errors.Is(err, odyexceptions.ErrSessionNotFound)` or compare two
// Errors by Code.
func (e *Error) Is(target error) bool {
	if e == nil || target == nil {
		return false
	}
	if t, ok := target.(*Error); ok {
		return e.Code == t.Code
	}
	if t, ok := target.(interface{ Code() Code }); ok {
		return e.Code == t.Code()
	}
	return false
}

// As sets target if target is a *Error and the chain matches. The standard
// errors.As walk-up happens automatically once Unwrap is implemented.
func (e *Error) As(target any) bool {
	if e == nil || target == nil {
		return false
	}
	if t, ok := target.(**Error); ok {
		*t = e
		return true
	}
	return false
}
