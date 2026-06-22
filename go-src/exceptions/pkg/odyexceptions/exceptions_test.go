// Tests for the odyexceptions package. Coverage:
//
//   - construction of each typed error (NewSessionNotFound, NewInvalidFileUpload,
//     NewLLMService, NewWebSearch)
//   - errors.Is matching against the Err* sentinels
//   - errors.As extraction of the typed *Error
//   - Wrap chains (Unwrap, errors.Is across the chain)
//   - Error message formatting (Error() output, Cause rendered)
//   - Code discriminator and String() mapping
//   - AsError convenience helper
//   - Cross-class non-matches (errors.Is does not match unrelated Codes)
package odyexceptions

import (
	"errors"
	"fmt"
	"strings"
	"testing"
)

// ---- Code.String() --------------------------------------------------------

func TestCodeString(t *testing.T) {
	cases := []struct {
		code Code
		want string
	}{
		{CodeUnknown, "unknown"},
		{CodeSessionNotFound, "session_not_found"},
		{CodeInvalidFileUpload, "invalid_file_upload"},
		{CodeLLMService, "llm_service"},
		{CodeWebSearch, "web_search"},
		{Code(9999), "unknown"},
	}
	for _, c := range cases {
		if got := c.code.String(); got != c.want {
			t.Errorf("Code(%d).String() = %q, want %q", c.code, got, c.want)
		}
	}
}

// ---- Construction ---------------------------------------------------------

func TestNewSessionNotFound(t *testing.T) {
	err := NewSessionNotFound("abc123")
	if err == nil {
		t.Fatal("NewSessionNotFound returned nil")
	}
	if err.Code != CodeSessionNotFound {
		t.Errorf("Code = %v, want %v", err.Code, CodeSessionNotFound)
	}
	if err.SessionID != "abc123" {
		t.Errorf("SessionID = %q, want abc123", err.SessionID)
	}
	wantMsg := "Session 'abc123' not found"
	if err.Message != wantMsg {
		t.Errorf("Message = %q, want %q", err.Message, wantMsg)
	}
	if err.Error() != "session_not_found: Session 'abc123' not found" {
		t.Errorf("Error() = %q", err.Error())
	}
	if err.Cause != nil {
		t.Errorf("Cause should be nil, got %v", err.Cause)
	}
}

func TestNewInvalidFileUpload(t *testing.T) {
	// With filename
	withName := NewInvalidFileUpload("too large", "big.csv")
	if withName.Code != CodeInvalidFileUpload {
		t.Errorf("Code = %v", withName.Code)
	}
	if withName.Message != "too large" {
		t.Errorf("Message = %q", withName.Message)
	}
	if withName.Filename != "big.csv" {
		t.Errorf("Filename = %q", withName.Filename)
	}
	// Without filename (Python: filename=None)
	noName := NewInvalidFileUpload("corrupt header", "")
	if noName.Code != CodeInvalidFileUpload {
		t.Errorf("Code = %v", noName.Code)
	}
	if noName.Filename != "" {
		t.Errorf("Filename = %q, want empty", noName.Filename)
	}
	if noName.Error() != "invalid_file_upload: corrupt header" {
		t.Errorf("Error() = %q", noName.Error())
	}
}

func TestNewLLMService(t *testing.T) {
	withEndpoint := NewLLMService("timeout", "https://api.example/v1")
	if withEndpoint.Code != CodeLLMService {
		t.Errorf("Code = %v", withEndpoint.Code)
	}
	if withEndpoint.Endpoint != "https://api.example/v1" {
		t.Errorf("Endpoint = %q", withEndpoint.Endpoint)
	}
	if withEndpoint.Error() != "llm_service: timeout" {
		t.Errorf("Error() = %q", withEndpoint.Error())
	}

	noEndpoint := NewLLMService("rate limit", "")
	if noEndpoint.Endpoint != "" {
		t.Errorf("Endpoint = %q, want empty", noEndpoint.Endpoint)
	}
}

func TestNewWebSearch(t *testing.T) {
	withQuery := NewWebSearch("upstream error", "odysseus ai")
	if withQuery.Code != CodeWebSearch {
		t.Errorf("Code = %v", withQuery.Code)
	}
	if withQuery.Query != "odysseus ai" {
		t.Errorf("Query = %q", withQuery.Query)
	}
	if withQuery.Error() != "web_search: upstream error" {
		t.Errorf("Error() = %q", withQuery.Error())
	}

	noQuery := NewWebSearch("network down", "")
	if noQuery.Query != "" {
		t.Errorf("Query = %q, want empty", noQuery.Query)
	}
}

// ---- errors.Is against sentinels -----------------------------------------

func TestErrorsIsSentinels(t *testing.T) {
	cases := []struct {
		name string
		err  error
		sent *Error
	}{
		{"session", NewSessionNotFound("s1"), ErrSessionNotFound},
		{"upload", NewInvalidFileUpload("bad", "f.txt"), ErrInvalidFileUpload},
		{"llm", NewLLMService("5xx", "https://x"), ErrLLMService},
		{"web", NewWebSearch("dns", "q"), ErrWebSearch},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if !errors.Is(c.err, c.sent) {
				t.Errorf("errors.Is(%v, %v) = false, want true", c.err, c.sent)
			}
		})
	}
}

func TestErrorsIsCrossClassNegative(t *testing.T) {
	// A SessionNotFound error must NOT match ErrLLMService (or any other
	// sentinel). errors.Is should walk by Code only, not by string match.
	snf := NewSessionNotFound("s1")
	others := []*Error{ErrInvalidFileUpload, ErrLLMService, ErrWebSearch}
	for _, o := range others {
		if errors.Is(snf, o) {
			t.Errorf("SessionNotFound incorrectly matched %v", o)
		}
	}
}

func TestErrorsIsNilSafe(t *testing.T) {
	var nilErr *Error
	if errors.Is(nilErr, ErrSessionNotFound) {
		t.Error("errors.Is(nil, ErrSessionNotFound) = true, want false")
	}
	if errors.Is(NewSessionNotFound("x"), nil) {
		t.Error("errors.Is(err, nil) = true, want false")
	}
}

// ---- errors.As extraction -------------------------------------------------

func TestErrorsAsExtractsTyped(t *testing.T) {
	original := NewLLMService("boom", "https://api.example/v1")
	wrapped := Wrap(original, CodeLLMService, "while streaming")

	var got *Error
	if !errors.As(wrapped, &got) {
		t.Fatal("errors.As returned false")
	}
	if got == nil {
		t.Fatal("errors.As set target to nil")
	}
	// errors.As finds the outermost matching *Error (the one we pass in), not
	// the deepest match in the chain. The outer wrapper carries the same Code
	// so callers can still branch on class.
	if got.Code != CodeLLMService {
		t.Errorf("Code = %v, want %v", got.Code, CodeLLMService)
	}
	// Walk the chain manually to confirm the typed cause is reachable.
	if inner := errors.Unwrap(wrapped); inner == nil {
		t.Error("expected wrapped to have an unwrap target")
	} else {
		var cause *Error
		if !errors.As(inner, &cause) {
			t.Error("errors.As did not find typed cause")
		} else if cause.Endpoint != "https://api.example/v1" {
			t.Errorf("typed cause.Endpoint = %q, want %q", cause.Endpoint, "https://api.example/v1")
		}
	}
}

func TestErrorsAsFailsForForeign(t *testing.T) {
	foreign := errors.New("some other library's error")
	var got *Error
	if errors.As(foreign, &got) {
		t.Error("errors.As matched a foreign error as *odyexceptions.Error")
	}
}

// ---- Wrap / Unwrap chain --------------------------------------------------

func TestWrapChainIsWalkable(t *testing.T) {
	// layer 1 (root): a network error from the standard library
	root := errors.New("dial tcp: timeout")

	// layer 2: typed LLMService that wraps root
	typed := Wrap(root, CodeLLMService, "LLM call failed")

	// layer 3: outer wrapper that adds context (using a plain *Error)
	outer := &Error{
		Code:    CodeLLMService,
		Message: "while answering user prompt",
		Cause:   typed,
	}

	// errors.Is should find the root cause through both layers.
	if !errors.Is(outer, root) {
		t.Error("errors.Is did not walk Wrap chain to root cause")
	}

	// errors.Is should match the typed sentinel at the top of the chain.
	if !errors.Is(outer, ErrLLMService) {
		t.Error("errors.Is did not match ErrLLMService through chain")
	}

	// errors.Unwrap returns the immediate next link.
	if got := errors.Unwrap(outer); got != typed {
		t.Errorf("Unwrap returned %v, want typed layer", got)
	}
	if got := errors.Unwrap(typed); got != root {
		t.Errorf("Unwrap returned %v, want root", got)
	}
	if got := errors.Unwrap(root); got != nil {
		t.Errorf("Unwrap on terminal error returned %v, want nil", got)
	}
}

func TestWrapNilReturnsNil(t *testing.T) {
	if got := Wrap(nil, CodeUnknown, ""); got != nil {
		t.Errorf("Wrap(nil) = %v, want nil", got)
	}
}

func TestUnwrapNilSafe(t *testing.T) {
	var nilErr *Error
	if got := nilErr.Unwrap(); got != nil {
		t.Errorf("nil Error Unwrap returned %v, want nil", got)
	}
	if got := nilErr.Error(); got != "<nil>" {
		t.Errorf("nil Error Error() returned %q, want <nil>", got)
	}
}

// ---- Error() formatting ---------------------------------------------------

func TestErrorFormatWithCause(t *testing.T) {
	cause := errors.New("connection refused")
	err := Wrap(cause, CodeLLMService, "stream interrupted")

	got := err.Error()
	want := "llm_service: stream interrupted: connection refused"
	if got != want {
		t.Errorf("Error() = %q, want %q", got, want)
	}
}

func TestErrorFormatNestedWrap(t *testing.T) {
	root := errors.New("eof")
	layer1 := Wrap(root, CodeLLMService, "decode failed")
	layer2 := Wrap(layer1, CodeLLMService, "agent loop")
	got := layer2.Error()

	// Each layer renders "code: message", joined by ": <cause>". The outermost
	// layer renders its code+message once, then the inner messages get appended
	// via Cause.Error() calls — so we just check the key fragments are present.
	for _, frag := range []string{
		"llm_service",
		"agent loop",
		"decode failed",
		"eof",
	} {
		if !strings.Contains(got, frag) {
			t.Errorf("Error() = %q missing fragment %q", got, frag)
		}
	}
}

func TestErrorImplementsErrorInterface(t *testing.T) {
	var _ error = (*Error)(nil)
	var _ error = NewSessionNotFound("x")
}

// ---- AsError convenience --------------------------------------------------

func TestAsErrorFindsTyped(t *testing.T) {
	original := NewSessionNotFound("xyz")
	wrapped := Wrap(original, CodeSessionNotFound, "outer")

	got := AsError(wrapped)
	if got == nil {
		t.Fatal("AsError returned nil")
	}
	if got.Code != CodeSessionNotFound {
		t.Errorf("Code = %v, want CodeSessionNotFound", got.Code)
	}
}

func TestAsErrorForeignReturnsNil(t *testing.T) {
	if got := AsError(errors.New("plain")); got != nil {
		t.Errorf("AsError(plain) = %v, want nil", got)
	}
	if got := AsError(nil); got != nil {
		t.Errorf("AsError(nil) = %v, want nil", got)
	}
}

// ---- Is on a plain foreign error (negative cross-check) -------------------

func TestIsFalseForForeignError(t *testing.T) {
	foreign := errors.New("some unrelated error")
	if errors.Is(foreign, ErrLLMService) {
		t.Error("errors.Is should not match foreign errors")
	}
}

// ---- NewError bare constructor -------------------------------------------

func TestNewErrorCarriesCodeAndMessage(t *testing.T) {
	e := NewError(CodeWebSearch, "manual")
	if e.Code != CodeWebSearch {
		t.Errorf("Code = %v", e.Code)
	}
	if e.Message != "manual" {
		t.Errorf("Message = %q", e.Message)
	}
	if e.Error() != "web_search: manual" {
		t.Errorf("Error() = %q", e.Error())
	}
}

// ---- Whole-hierarchy demo (sanity sweep) ---------------------------------

func TestAllSentinelsAreDistinct(t *testing.T) {
	sentinels := []*Error{ErrSessionNotFound, ErrInvalidFileUpload, ErrLLMService, ErrWebSearch}
	seen := make(map[Code]bool)
	for _, s := range sentinels {
		if seen[s.Code] {
			t.Errorf("duplicate Code %v among sentinels", s.Code)
		}
		seen[s.Code] = true
	}
	if len(seen) != 4 {
		t.Errorf("expected 4 distinct codes, got %d", len(seen))
	}
}

// ---- Per-class structural fields survive through Wrap --------------------

func TestStructuredFieldsSurviveWrap(t *testing.T) {
	cases := []struct {
		name string
		err  *Error
		chk  func(*Error) bool
		frag string // substring expected in Error()
	}{
		{
			name: "SessionID",
			err:  NewSessionNotFound("s-42"),
			chk:  func(e *Error) bool { return e.SessionID == "s-42" },
			frag: "Session 's-42' not found",
		},
		{
			name: "Filename",
			err:  NewInvalidFileUpload("too big", "huge.zip"),
			chk:  func(e *Error) bool { return e.Filename == "huge.zip" },
			frag: "too big",
		},
		{
			name: "Endpoint",
			err:  NewLLMService("timeout", "https://api/v1"),
			chk:  func(e *Error) bool { return e.Endpoint == "https://api/v1" },
			frag: "timeout",
		},
		{
			name: "Query",
			err:  NewWebSearch("dns", "go exceptions"),
			chk:  func(e *Error) bool { return e.Query == "go exceptions" },
			frag: "dns",
		},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if !c.chk(c.err) {
				t.Errorf("structured field check failed for %s", c.name)
			}
			if !strings.Contains(c.err.Error(), c.frag) {
				t.Errorf("Error() = %q missing fragment %q", c.err.Error(), c.frag)
			}
			// Wrap should preserve the Code so errors.Is still works.
			wrapped := Wrap(c.err, c.err.Code, "wrapped")
			if !errors.Is(wrapped, c.err) {
				t.Errorf("errors.Is did not match after Wrap for %s", c.name)
			}
		})
	}
}

// ---- Format chain ends with formatted code/msg --------------------------

func TestErrorChainFormatDoesNotPanic(t *testing.T) {
	defer func() {
		if r := recover(); r != nil {
			t.Fatalf("Error() panicked: %v", r)
		}
	}()

	// Deep nesting to catch any recursion guards we might be missing.
	var err error = errors.New("terminal")
	for i := 0; i < 50; i++ {
		err = Wrap(err, CodeLLMService, fmt.Sprintf("layer-%d", i))
	}
	_ = err.Error()
}
