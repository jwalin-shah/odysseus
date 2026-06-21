package upload_limits

import (
	"bytes"
	"errors"
	"io"
	"strings"
	"testing"
)

func TestReadUploadLimited_UnderLimit(t *testing.T) {
	src := bytes.NewReader([]byte("hello world"))
	got, err := ReadUploadLimited(src, 100, "Test")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if string(got) != "hello world" {
		t.Errorf("got %q, want %q", got, "hello world")
	}
}

func TestReadUploadLimited_ExactlyAtLimit(t *testing.T) {
	payload := bytes.Repeat([]byte("a"), 50)
	src := bytes.NewReader(payload)
	got, err := ReadUploadLimited(src, 50, "Test")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !bytes.Equal(got, payload) {
		t.Errorf("got %d bytes, want %d bytes", len(got), len(payload))
	}
}

func TestReadUploadLimited_OneOverLimit(t *testing.T) {
	payload := bytes.Repeat([]byte("a"), 51)
	src := bytes.NewReader(payload)
	_, err := ReadUploadLimited(src, 50, "Test")
	if err == nil {
		t.Fatal("expected ErrUploadTooLarge, got nil")
	}
	if !errors.Is(err, ErrUploadTooLarge) {
		t.Errorf("error %v should wrap ErrUploadTooLarge", err)
	}
	if !strings.Contains(err.Error(), "50 bytes") {
		t.Errorf("error %q should contain formatted limit", err)
	}
	if !strings.Contains(err.Error(), "Test") {
		t.Errorf("error %q should contain label", err)
	}
}

func TestReadUploadLimited_ZeroByteRead(t *testing.T) {
	src := bytes.NewReader(nil)
	got, err := ReadUploadLimited(src, 1024, "Empty")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 0 {
		t.Errorf("got %d bytes, want 0", len(got))
	}
}

func TestReadUploadLimited_DefaultLabelWhenEmpty(t *testing.T) {
	src := bytes.NewReader([]byte("ok"))
	_, err := ReadUploadLimited(src, 1, "")
	if err == nil {
		t.Fatal("expected error on over-limit")
	}
	if !strings.Contains(err.Error(), "Upload") {
		t.Errorf("error %q should use default label 'Upload'", err)
	}
}

func TestReadUploadLimited_PropagatesReaderError(t *testing.T) {
	r := &errReader{err: io.ErrUnexpectedEOF}
	_, err := ReadUploadLimited(r, 100, "Test")
	if err == nil {
		t.Fatal("expected error to propagate")
	}
	if !errors.Is(err, io.ErrUnexpectedEOF) {
		t.Errorf("expected io.ErrUnexpectedEOF, got %v", err)
	}
}

func TestReadUploadLimited_RejectsZeroLimit(t *testing.T) {
	_, err := ReadUploadLimited(bytes.NewReader(nil), 0, "Test")
	if err == nil {
		t.Fatal("expected error for zero limit")
	}
}

func TestReadUploadLimited_RejectsNegativeLimit(t *testing.T) {
	_, err := ReadUploadLimited(bytes.NewReader(nil), -1, "Test")
	if err == nil {
		t.Fatal("expected error for negative limit")
	}
}

func TestReadUploadLimited_LargePayloadFormat(t *testing.T) {
	// 2 MB payload into a 1 MB limit — error message should use MB suffix.
	payload := bytes.Repeat([]byte("x"), 2*1024*1024)
	_, err := ReadUploadLimited(bytes.NewReader(payload), 1024*1024, "Big")
	if !errors.Is(err, ErrUploadTooLarge) {
		t.Fatalf("expected ErrUploadTooLarge, got %v", err)
	}
	if !strings.Contains(err.Error(), "1 MB") {
		t.Errorf("error %q should format limit as '1 MB'", err)
	}
}

// errReader is a minimal io.Reader that always returns the configured error.
type errReader struct{ err error }

func (r *errReader) Read(p []byte) (int, error) { return 0, r.err }
