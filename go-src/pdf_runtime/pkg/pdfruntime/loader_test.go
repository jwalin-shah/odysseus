package pdfruntime

import (
	"errors"
	"strings"
	"testing"
)

func TestMissingMessage_Stable(t *testing.T) {
	// The Python source treats PDF_VIEWER_PYMUPDF_MISSING as a constant
	// string that operators grep for in logs. Mirror that contract: the
	// Go port's MissingMessage must contain the same phrases.
	for _, frag := range []string{
		"PDF viewer requires PyMuPDF",
		"requirements-optional.txt",
		"AGPL-3.0",
	} {
		if !strings.Contains(MissingMessage, frag) {
			t.Errorf("MissingMessage missing %q: %q", frag, MissingMessage)
		}
	}
}

func TestMissingError_ErrorsIs(t *testing.T) {
	err := MissingError(errors.New("underlying"))
	if !errors.Is(err, ErrMissing) {
		t.Errorf("errors.Is(err, ErrMissing) = false, want true")
	}
	// Nil cause is fine.
	if err2 := MissingError(nil); !errors.Is(err2, ErrMissing) {
		t.Errorf("errors.Is(MissingError(nil), ErrMissing) = false, want true")
	}
}

func TestMissingError_Unwrap(t *testing.T) {
	cause := errors.New("underlying cause")
	err := MissingError(cause)
	if got := errors.Unwrap(err); got != cause {
		t.Errorf("Unwrap = %v, want %v", got, cause)
	}
}

func TestMissingError_MessageFormat(t *testing.T) {
	err := MissingError(nil)
	if err.Error() != MissingMessage {
		t.Errorf("Error() = %q, want %q", err.Error(), MissingMessage)
	}
}

func TestStaticLoader_ReturnsValue(t *testing.T) {
	loader := StaticLoader{Value: "fitz-handle"}
	v, err := loader.Load()
	if err != nil {
		t.Fatalf("Load returned err: %v", err)
	}
	if v != "fitz-handle" {
		t.Errorf("Load = %v, want fitz-handle", v)
	}
}

func TestFailingLoader_ReturnsMissingError(t *testing.T) {
	loader := FailingLoader{}
	v, err := loader.Load()
	if v != nil {
		t.Errorf("Load value = %v, want nil", v)
	}
	if !errors.Is(err, ErrMissing) {
		t.Errorf("errors.Is(err, ErrMissing) = false, want true (err=%v)", err)
	}
	if !strings.Contains(err.Error(), "PyMuPDF") {
		t.Errorf("error message should mention PyMuPDF: %q", err.Error())
	}
}

func TestFuncLoader_Delegates(t *testing.T) {
	want := errors.New("boom")
	called := 0
	loader := FuncLoader(func() (any, error) {
		called++
		return "ok", want
	})
	v, err := loader.Load()
	if called != 1 {
		t.Errorf("called = %d, want 1", called)
	}
	if v != "ok" {
		t.Errorf("value = %v, want ok", v)
	}
	if !errors.Is(err, want) {
		t.Errorf("err = %v, want %v", err, want)
	}
}

func TestFuncLoader_NilFunc(t *testing.T) {
	// A nil closure would panic — but LoaderFunc(nil) is still a valid
	// type and the call should propagate the panic, not return silently.
	defer func() {
		if r := recover(); r == nil {
			t.Errorf("expected panic from nil func, got none")
		}
	}()
	var fn LoaderFunc
	_, _ = fn.Load()
}

func TestErrMissing_Equality(t *testing.T) {
	// ErrMissing should be a stable sentinel callers can compare against
	// directly (e.g. `if err == pdfruntime.ErrMissing`). errors.Is also
	// works because it falls back to == when target is not comparable
	// via Is method.
	if ErrMissing == nil {
		t.Fatal("ErrMissing is nil")
	}
	if !errors.Is(ErrMissing, ErrMissing) {
		t.Errorf("errors.Is(ErrMissing, ErrMissing) = false, want true")
	}
}
