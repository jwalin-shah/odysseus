// Package odyexceptions — per-class constructors and package-level sentinel
// errors. These are the public surface that mirrors the four Python exception
// classes declared in src/exceptions.py.
package odyexceptions

import "fmt"

// ErrSessionNotFound is the package-level sentinel callers match against with
// errors.Is. Mirrors `src.exceptions.SessionNotFoundError`.
var ErrSessionNotFound = &Error{Code: CodeSessionNotFound, Message: "session not found"}

// ErrInvalidFileUpload is the package-level sentinel for the file-upload
// validation exception. Mirrors `src.exceptions.InvalidFileUploadError`.
var ErrInvalidFileUpload = &Error{Code: CodeInvalidFileUpload, Message: "invalid file upload"}

// ErrLLMService is the package-level sentinel for LLM transport errors.
// Mirrors `src.exceptions.LLMServiceError`.
var ErrLLMService = &Error{Code: CodeLLMService, Message: "llm service error"}

// ErrWebSearch is the package-level sentinel for web-search failures.
// Mirrors `src.exceptions.WebSearchError`.
var ErrWebSearch = &Error{Code: CodeWebSearch, Message: "web search error"}

// NewSessionNotFound mirrors SessionNotFoundError(session_id) in Python. The
// returned Error has Code=CodeSessionNotFound and Message="Session '<id>' not
// found".
func NewSessionNotFound(sessionID string) *Error {
	return &Error{
		Code:      CodeSessionNotFound,
		Message:   fmt.Sprintf("Session '%s' not found", sessionID),
		SessionID: sessionID,
	}
}

// NewInvalidFileUpload mirrors InvalidFileUploadError(message, filename). The
// filename is optional and the field is left empty when not supplied.
func NewInvalidFileUpload(message string, filename string) *Error {
	return &Error{
		Code:     CodeInvalidFileUpload,
		Message:  message,
		Filename: filename,
	}
}

// NewLLMService mirrors LLMServiceError(message, endpoint). The endpoint is
// optional and the field is left empty when not supplied.
func NewLLMService(message string, endpoint string) *Error {
	return &Error{
		Code:     CodeLLMService,
		Message:  message,
		Endpoint: endpoint,
	}
}

// NewWebSearch mirrors WebSearchError(message, query). The query is optional
// and the field is left empty when not supplied.
func NewWebSearch(message string, query string) *Error {
	return &Error{
		Code:    CodeWebSearch,
		Message: message,
		Query:   query,
	}
}

// Wrap attaches a cause to err and returns a new *Error with the same Code.
// A nil err yields nil. A non-*Error target is preserved as the cause but the
// returned error always carries the typed Code from the original *Error so
// errors.Is(err, ErrFoo) still matches.
func Wrap(err error, code Code, msg string) *Error {
	if err == nil {
		return nil
	}
	return &Error{
		Code:    code,
		Message: msg,
		Cause:   err,
	}
}

// NewError constructs a bare-bones *Error with the given Code and Message.
// Use this when the structured per-class fields don't apply. Most callers
// should prefer the New* constructors above so the right Code is set
// automatically.
func NewError(code Code, msg string) *Error {
	return &Error{Code: code, Message: msg}
}

// AsError returns the receiver typed as *Error when err is one of our typed
// errors (including anything in its Unwrap chain), or nil otherwise. Mirrors
// the convenience Python callers get when catching by base class.
func AsError(err error) *Error {
	if err == nil {
		return nil
	}
	var e *Error
	if errorsAs(err, &e) {
		return e
	}
	return nil
}
