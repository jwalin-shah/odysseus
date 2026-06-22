package main

import (
	"bytes"
	"strings"
	"testing"

	"odysseus/api_key_manager"
)

func TestRun_PrintsPathsAndReadsStdinForEncryptDecrypt(t *testing.T) {
	dir := t.TempDir()

	// First invocation: --encrypt a value via stdin.
	encryptOut := &bytes.Buffer{}
	encryptErr := &bytes.Buffer{}
	if err := run(
		[]string{"--data-dir", dir, "--encrypt"},
		strings.NewReader("sk-test-cli"),
		encryptOut, encryptErr,
	); err != nil {
		t.Fatalf("encrypt run: %v (stderr=%q)", err, encryptErr.String())
	}
	encLine := extractLast(encryptOut.String(), "encrypted: ")
	if encLine == "" {
		t.Fatalf("no encrypted: line in output: %q", encryptOut.String())
	}

	// Second invocation: --decrypt the captured token in the same dir.
	decryptOut := &bytes.Buffer{}
	decryptErr := &bytes.Buffer{}
	if err := run(
		[]string{"--data-dir", dir, "--decrypt"},
		strings.NewReader(encLine),
		decryptOut, decryptErr,
	); err != nil {
		t.Fatalf("decrypt run: %v (stderr=%q)", err, decryptErr.String())
	}
	if !strings.Contains(decryptOut.String(), "decrypted: sk-test-cli") {
		t.Fatalf("expected decrypted output to contain the plaintext; got %q", decryptOut.String())
	}
}

func TestRun_MutuallyExclusiveFlags(t *testing.T) {
	err := run(
		[]string{"--data-dir", t.TempDir(), "--encrypt", "--decrypt"},
		strings.NewReader(""),
		&bytes.Buffer{}, &bytes.Buffer{},
	)
	if err == nil {
		t.Fatal("expected error when both --encrypt and --decrypt are passed")
	}
	if !strings.Contains(err.Error(), "one of --encrypt or --decrypt") {
		t.Fatalf("err = %v, want mutually-exclusive error", err)
	}
}

// Sanity check: an empty stdin should still print the paths and not error.
func TestRun_EmptyStdin(t *testing.T) {
	out := &bytes.Buffer{}
	if err := run(
		[]string{"--data-dir", t.TempDir()},
		strings.NewReader(""),
		out, &bytes.Buffer{},
	); err != nil {
		t.Fatalf("empty stdin: %v", err)
	}
	for _, want := range []string{"data_dir:", "key_file:", "keys_file:"} {
		if !strings.Contains(out.String(), want) {
			t.Fatalf("output missing %q: %q", want, out.String())
		}
	}
}

// extractLast returns the substring after the last occurrence of prefix in s,
// up to the next newline (or end of string). Empty if not found.
func extractLast(s, prefix string) string {
	idx := strings.LastIndex(s, prefix)
	if idx < 0 {
		return ""
	}
	rest := s[idx+len(prefix):]
	if nl := strings.IndexByte(rest, '\n'); nl >= 0 {
		rest = rest[:nl]
	}
	return strings.TrimRight(rest, "\r")
}

var _ = api_key_manager.NewManager // keep import live for future CLI tests
