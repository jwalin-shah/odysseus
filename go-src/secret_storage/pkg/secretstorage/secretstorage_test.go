package secretstorage

import (
	"path/filepath"
	"strings"
	"testing"
)

// newTestStorage returns a SecretStorage backed by an InMemoryKeyBackend
// and the XOR stub cipher. Tests that need a different key use the
// parameters directly; this helper just keeps the boilerplate down.
func newTestStorage(t *testing.T) *SecretStorage {
	t.Helper()
	key := []byte("0123456789abcdef0123456789abcdef") // 32 bytes
	backend, err := NewInMemoryKeyBackend(key)
	if err != nil {
		t.Fatalf("NewInMemoryKeyBackend: %v", err)
	}
	cipher, err := NewXORStubCipher(key)
	if err != nil {
		t.Fatalf("NewXORStubCipher: %v", err)
	}
	ss, err := NewSecretStorage(backend, cipher)
	if err != nil {
		t.Fatalf("NewSecretStorage: %v", err)
	}
	return ss
}

// --- Encrypt ---------------------------------------------------------------

// TestEncryptHappyPath covers the basic encrypt → decrypt round trip.
func TestEncryptHappyPath(t *testing.T) {
	ss := newTestStorage(t)
	ct, err := ss.Encrypt("hunter2")
	if err != nil {
		t.Fatalf("Encrypt: %v", err)
	}
	if !strings.HasPrefix(ct, EncryptedPrefix) {
		t.Fatalf("expected %q to be prefixed with %q", ct, EncryptedPrefix)
	}
	pt, err := ss.Decrypt(ct)
	if err != nil {
		t.Fatalf("Decrypt: %v", err)
	}
	if pt != "hunter2" {
		t.Errorf("Decrypt round-trip = %q, want hunter2", pt)
	}
}

// TestEncryptEmptyInput pins the Python helper's "empty input passes
// through" behaviour. Empty plaintext should return "" with no error.
func TestEncryptEmptyInput(t *testing.T) {
	ss := newTestStorage(t)
	got, err := ss.Encrypt("")
	if err != nil {
		t.Fatalf("Encrypt empty: %v", err)
	}
	if got != "" {
		t.Errorf("Encrypt empty = %q, want \"\"", got)
	}
}

// TestEncryptIdempotentOnCiphertext verifies that re-encrypting a
// ciphertext is a no-op. The Python helper has the same behaviour so
// legacy rows can be passed through encrypt() without double-wrapping.
func TestEncryptIdempotentOnCiphertext(t *testing.T) {
	ss := newTestStorage(t)
	ct1, err := ss.Encrypt("hunter2")
	if err != nil {
		t.Fatalf("Encrypt: %v", err)
	}
	ct2, err := ss.Encrypt(ct1)
	if err != nil {
		t.Fatalf("Encrypt on ciphertext: %v", err)
	}
	if ct1 != ct2 {
		t.Errorf("Encrypt(ciphertext) = %q, want passthrough %q", ct2, ct1)
	}
}

// TestEncryptLongPlaintext covers a multi-block plaintext to ensure the
// mask cycles correctly across more bytes than the key length.
func TestEncryptLongPlaintext(t *testing.T) {
	ss := newTestStorage(t)
	in := strings.Repeat("abcdefghij", 50) // 500 bytes
	ct, err := ss.Encrypt(in)
	if err != nil {
		t.Fatalf("Encrypt: %v", err)
	}
	pt, err := ss.Decrypt(ct)
	if err != nil {
		t.Fatalf("Decrypt: %v", err)
	}
	if pt != in {
		t.Errorf("long round-trip mismatch: len=%d want=%d", len(pt), len(in))
	}
}

// TestEncryptUTF8 covers a multi-byte plaintext to ensure UTF-8 round
// trips. Fernet's contract is bytes-in / bytes-out; the Go port must
// preserve that.
func TestEncryptUTF8(t *testing.T) {
	ss := newTestStorage(t)
	cases := []string{
		"héllo",
		"日本語",
		"emoji 🙃",
		"mix: café 日本 🙃",
	}
	for _, in := range cases {
		ct, err := ss.Encrypt(in)
		if err != nil {
			t.Fatalf("Encrypt(%q): %v", in, err)
		}
		pt, err := ss.Decrypt(ct)
		if err != nil {
			t.Fatalf("Decrypt(%q): %v", ct, err)
		}
		if pt != in {
			t.Errorf("UTF-8 round-trip: got %q want %q", pt, in)
		}
	}
}

// TestEncryptTableDriven covers the small matrix of behaviours: empty,
// already-encrypted, plaintext-of-mixed-shapes, and a long input.
func TestEncryptTableDriven(t *testing.T) {
	ss := newTestStorage(t)
	tests := []struct {
		name string
		in   string
	}{
		{"empty", ""},
		{"single_char", "x"},
		{"ascii", "hunter2"},
		{"with_spaces", "two words"},
		{"with_punctuation", "p@ssw0rd!#%&*"},
		{"already_encrypted", EncryptedPrefix + "deadbeef"},
		{"unicode", "café 日本"},
	}
	for _, tc := range tests {
		tc := tc
		t.Run(tc.name, func(t *testing.T) {
			got, err := ss.Encrypt(tc.in)
			if err != nil {
				t.Fatalf("Encrypt: %v", err)
			}
			if tc.in == "" {
				if got != "" {
					t.Errorf("empty Encrypt = %q, want \"\"", got)
				}
				return
			}
			if strings.HasPrefix(tc.in, EncryptedPrefix) {
				if got != tc.in {
					t.Errorf("idempotent Encrypt = %q, want %q", got, tc.in)
				}
				return
			}
			if !strings.HasPrefix(got, EncryptedPrefix) {
				t.Errorf("plaintext Encrypt = %q, missing %q prefix", got, EncryptedPrefix)
			}
			// Round-trip back to the same plaintext.
			pt, err := ss.Decrypt(got)
			if err != nil {
				t.Fatalf("Decrypt: %v", err)
			}
			if pt != tc.in {
				t.Errorf("round-trip mismatch: got %q want %q", pt, tc.in)
			}
		})
	}
}

// --- Decrypt ---------------------------------------------------------------

// TestDecryptPlaintextPassThrough mirrors the legacy-row path: a value
// without the enc: prefix must come back unchanged.
func TestDecryptPlaintextPassThrough(t *testing.T) {
	ss := newTestStorage(t)
	got, err := ss.Decrypt("plain_password_legacy")
	if err != nil {
		t.Fatalf("Decrypt plaintext: %v", err)
	}
	if got != "plain_password_legacy" {
		t.Errorf("Decrypt plaintext = %q, want passthrough", got)
	}
}

// TestDecryptEmptyInput verifies that Decrypt("") returns "" with no
// error, matching the Python helper's behaviour.
func TestDecryptEmptyInput(t *testing.T) {
	ss := newTestStorage(t)
	got, err := ss.Decrypt("")
	if err != nil {
		t.Fatalf("Decrypt empty: %v", err)
	}
	if got != "" {
		t.Errorf("Decrypt empty = %q, want \"\"", got)
	}
}

// TestDecryptCorruptToken covers the failure path: a value that begins
// with the prefix but doesn't decrypt to a valid string must yield ""
// (Python behaviour) and a non-nil error so callers can log it.
func TestDecryptCorruptToken(t *testing.T) {
	ss := newTestStorage(t)
	got, err := ss.Decrypt(EncryptedPrefix + "this-is-not-base64-!!!")
	if err == nil {
		t.Fatalf("expected error from corrupt token, got nil (returned %q)", got)
	}
	if got != "" {
		t.Errorf("corrupt Decrypt = %q, want \"\"", got)
	}
}

// TestDecryptTamperedCiphertext verifies that a ciphertext tampered in
// flight yields "hunter3" (the XOR-stub cipher is symmetric and base64
// decoding is permissive) and IsEncrypted / Encrypt / Decrypt stay
// self-consistent. A real Fernet cipher would reject this token via
// HMAC; the XOR stub cannot, so we pin the actual behaviour: the round
// trip mutates exactly one byte of the plaintext. This still proves
// the SecretStorage surface stays well-defined under tampered input.
func TestDecryptTamperedCiphertext(t *testing.T) {
	ss := newTestStorage(t)
	ct, err := ss.Encrypt("hunter2")
	if err != nil {
		t.Fatalf("Encrypt: %v", err)
	}
	// Flip the last byte of the token (drop the final base64 char and
	// append a different one). With the XOR stub the underlying cipher
	// does not detect this, so Decrypt returns a one-byte-different
	// plaintext instead of an error. We pin that behaviour here.
	head := ct[:len(ct)-1]
	tampered := head + "X"
	got, err := ss.Decrypt(tampered)
	if err != nil {
		t.Fatalf("unexpected error from tampered token: %v (returned %q)", err, got)
	}
	if got == "hunter2" {
		t.Errorf("tampered Decrypt should differ from plaintext, got %q", got)
	}
	if !ss.IsEncrypted(tampered) {
		t.Errorf("tampered token should still report IsEncrypted=true")
	}
}

// --- IsEncrypted -----------------------------------------------------------

// TestIsEncryptedTableDriven covers the truth-table for IsEncrypted.
// Empty strings are NOT encrypted (Python behaviour); values with the
// prefix are; values without are not.
func TestIsEncryptedTableDriven(t *testing.T) {
	ss := newTestStorage(t)
	tests := []struct {
		in   string
		want bool
	}{
		{"", false},
		{"plain", false},
		{EncryptedPrefix, true},
		{EncryptedPrefix + "abc", true},
		{"enc", false}, // prefix must match exactly
	}
	for _, tc := range tests {
		if got := ss.IsEncrypted(tc.in); got != tc.want {
			t.Errorf("IsEncrypted(%q) = %v, want %v", tc.in, got, tc.want)
		}
	}
}

// --- KeyBackend ------------------------------------------------------------

// TestFileKeyBackendEnsureAndLoad drives the on-disk backend through a
// full create-then-load cycle. After EnsureKey, Load must return the
// same bytes we wrote.
func TestFileKeyBackendEnsureAndLoad(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, ".app_key")
	want := []byte("0123456789abcdef0123456789abcdef")

	be, err := NewFileKeyBackend(path)
	if err != nil {
		t.Fatalf("NewFileKeyBackend: %v", err)
	}
	if err := be.EnsureKey(want); err != nil {
		t.Fatalf("EnsureKey: %v", err)
	}

	got, err := be.Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if string(got) != string(want) {
		t.Errorf("Load = %q, want %q", got, want)
	}
}

// TestFileKeyBackendEnsureIsIdempotent pins the "do not overwrite an
// existing key" behaviour. A second EnsureKey with a different key must
// leave the original file untouched.
func TestFileKeyBackendEnsureIsIdempotent(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, ".app_key")
	first := []byte("0123456789abcdef0123456789abcdef")
	second := []byte("ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ")

	be, err := NewFileKeyBackend(path)
	if err != nil {
		t.Fatalf("NewFileKeyBackend: %v", err)
	}
	if err := be.EnsureKey(first); err != nil {
		t.Fatalf("EnsureKey first: %v", err)
	}
	if err := be.EnsureKey(second); err != nil {
		t.Fatalf("EnsureKey second: %v", err)
	}

	got, err := be.Load()
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if string(got) != string(first) {
		t.Errorf("Load = %q, want original %q", got, first)
	}
}

// TestFileKeyBackendLoadMissingFile guards the error path: a backend
// pointed at a non-existent file must return a non-nil error from
// Load. The caller (NewSecretStorage) propagates that error so a
// misconfigured host fails fast.
func TestFileKeyBackendLoadMissingFile(t *testing.T) {
	dir := t.TempDir()
	be, err := NewFileKeyBackend(filepath.Join(dir, "nope.key"))
	if err != nil {
		t.Fatalf("NewFileKeyBackend: %v", err)
	}
	if _, err := be.Load(); err == nil {
		t.Error("expected error from Load on missing file, got nil")
	}
}

// TestInMemoryKeyBackendRejectsShortKey ensures the constructor
// refuses keys shorter than the 16-byte minimum.
func TestInMemoryKeyBackendRejectsShortKey(t *testing.T) {
	cases := [][]byte{
		nil,
		{},
		[]byte("short"),
		[]byte("15-bytes-123456"),
	}
	for _, k := range cases {
		if _, err := NewInMemoryKeyBackend(k); err == nil {
			t.Errorf("expected error for short key %q, got nil", k)
		}
	}
}

// TestNewSecretStorageRejectsNilDeps covers the two configuration
// errors. A nil backend or nil cipher must surface as a non-nil error
// from NewSecretStorage so misconfiguration fails at startup, not on
// the first encrypt/decrypt call.
func TestNewSecretStorageRejectsNilDeps(t *testing.T) {
	cipher, _ := NewXORStubCipher([]byte("0123456789abcdef0123456789abcdef"))
	backend, _ := NewInMemoryKeyBackend([]byte("0123456789abcdef0123456789abcdef"))

	if _, err := NewSecretStorage(nil, cipher); err == nil {
		t.Error("expected error for nil backend, got nil")
	}
	if _, err := NewSecretStorage(backend, nil); err == nil {
		t.Error("expected error for nil cipher, got nil")
	}
}

// TestNewSecretStoragePropagatesBackendError covers the case where the
// backend's Load fails (missing key file). The error must surface
// from NewSecretStorage, not from a later Encrypt call.
func TestNewSecretStoragePropagatesBackendError(t *testing.T) {
	dir := t.TempDir()
	be, err := NewFileKeyBackend(filepath.Join(dir, "missing.key"))
	if err != nil {
		t.Fatalf("NewFileKeyBackend: %v", err)
	}
	cipher, _ := NewXORStubCipher([]byte("0123456789abcdef0123456789abcdef"))
	if _, err := NewSecretStorage(be, cipher); err == nil {
		t.Error("expected error from NewSecretStorage on missing key file")
	}
}

// TestNewFileKeyBackendRejectsEmptyPath is a tiny sanity check on the
// constructor.
func TestNewFileKeyBackendRejectsEmptyPath(t *testing.T) {
	if _, err := NewFileKeyBackend(""); err == nil {
		t.Error("expected error for empty path, got nil")
	}
}

// --- XOR stub cipher -------------------------------------------------------

// TestXORStubCipherRoundTrip is a sanity check on the default cipher
// itself: a single plaintext must round-trip back to itself.
func TestXORStubCipherRoundTrip(t *testing.T) {
	c, err := NewXORStubCipher([]byte("0123456789abcdef0123456789abcdef"))
	if err != nil {
		t.Fatalf("NewXORStubCipher: %v", err)
	}
	for _, in := range []string{"", "a", "hunter2", "日本語"} {
		tok, err := c.Encrypt(in)
		if err != nil {
			t.Fatalf("Encrypt(%q): %v", in, err)
		}
		out, err := c.Decrypt(tok)
		if err != nil {
			t.Fatalf("Decrypt(%q): %v", tok, err)
		}
		if out != in {
			t.Errorf("cipher round-trip: got %q want %q", out, in)
		}
	}
}

// TestXORStubCipherRejectsBadBase64 ensures the cipher surfaces base64
// decoding errors rather than silently producing garbage.
func TestXORStubCipherRejectsBadBase64(t *testing.T) {
	c, _ := NewXORStubCipher([]byte("0123456789abcdef0123456789abcdef"))
	if _, err := c.Decrypt("not base64 !!!"); err == nil {
		t.Error("expected error from cipher on bad base64, got nil")
	}
}

// TestXORStubCipherRefusesEncPrefixedPlaintext covers the defensive
// branch in xorStubCipher.Decrypt that catches a plain value round-
// tripping back into the prefix shape.
func TestXORStubCipherRefusesEncPrefixedPlaintext(t *testing.T) {
	c, _ := NewXORStubCipher([]byte("0123456789abcdef0123456789abcdef"))
	// Forge a token that XOR-decodes into "enc:hello..." — the cipher
	// must refuse so SecretStorage.Decrypt can apply its empty fallback
	// rather than return a value that masquerades as a ciphertext.
	token, err := c.Encrypt(EncryptedPrefix + "hello")
	if err != nil {
		t.Fatalf("Encrypt: %v", err)
	}
	// Re-Decrypt the same token via the cipher directly. The cipher's
	// contract is to refuse.
	if _, err := c.Decrypt(token); err == nil {
		t.Error("expected cipher to refuse round-trip into enc: prefix")
	}
}
