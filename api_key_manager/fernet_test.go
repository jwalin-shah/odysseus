package api_key_manager

import (
	"bytes"
	"encoding/base64"
	"errors"
	"testing"
	"time"
)

// TestFernetRoundTrip encrypts and decrypts a representative plaintext with a
// known key and asserts the bytes come back identical. The timestamp is held
// constant so the result is deterministic across runs.
func TestFernetRoundTrip(t *testing.T) {
	key := mustKey(t, "ZORv1Peaqz48dbQzzv9LmVu2qvOE5TPvxN8Qr0k7pZw=")
	cases := [][]byte{
		[]byte(""),
		[]byte("a"),
		[]byte("hello world"),
		bytes.Repeat([]byte{0x42}, 31),  // one byte short of a 32-byte block
		bytes.Repeat([]byte{0x42}, 32),  // exactly one block
		bytes.Repeat([]byte{0x42}, 100), // spans multiple blocks
	}
	for _, plain := range cases {
		label := string(plain)
		if len(label) > 20 {
			label = label[:20]
		}
		t.Run(label, func(t *testing.T) {
			now := time.Unix(1_700_000_000, 0)
			tok, err := Encrypt(key, plain, now)
			if err != nil {
				t.Fatalf("encrypt: %v", err)
			}
			got, err := Decrypt(key, tok, now)
			if err != nil {
				t.Fatalf("decrypt: %v", err)
			}
			if !bytes.Equal(got, plain) {
				t.Fatalf("round-trip mismatch: got %q want %q", got, plain)
			}
		})
	}
}

// TestFernetGenerateKeyRoundTrip generates a key with GenerateKey, then
// encrypts and decrypts under it. Catches accidental reliance on a hardcoded
// key.
func TestFernetGenerateKeyRoundTrip(t *testing.T) {
	key, err := GenerateKey()
	if err != nil {
		t.Fatalf("generate key: %v", err)
	}
	if len(key) != fernetKeyB64Len {
		t.Fatalf("generated key length %d, want %d", len(key), fernetKeyB64Len)
	}
	tok, err := Encrypt(key, []byte("rotate me"), time.Now())
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}
	got, err := Decrypt(key, tok, time.Now())
	if err != nil {
		t.Fatalf("decrypt: %v", err)
	}
	if string(got) != "rotate me" {
		t.Fatalf("got %q want %q", got, "rotate me")
	}
}

// TestFernetTamperedCiphertextFails flips a bit inside the base64 token. The
// HMAC check fires before decryption, so any tamper should produce
// ErrInvalidToken regardless of which region was hit.
func TestFernetTamperedCiphertextFails(t *testing.T) {
	key := mustKey(t, "ZORv1Peaqz48dbQzzv9LmVu2qvOE5TPvxN8Qr0k7pZw=")
	now := time.Unix(1_700_000_000, 0)
	tok, err := Encrypt(key, []byte("important secret"), now)
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}
	bad := []byte(tok)
	bad[len(bad)/2] ^= 0x01
	if _, err := Decrypt(key, bad, now); !errors.Is(err, ErrInvalidToken) {
		t.Fatalf("tampered token decrypt err = %v, want ErrInvalidToken", err)
	}
}

// TestFernetTamperedHMACFails flips a byte in the trailing HMAC region
// (after decoding). The constant-time compare must catch the mismatch.
func TestFernetTamperedHMACFails(t *testing.T) {
	key := mustKey(t, "ZORv1Peaqz48dbQzzv9LmVu2qvOE5TPvxN8Qr0k7pZw=")
	now := time.Unix(1_700_000_000, 0)
	tok, err := Encrypt(key, []byte("important secret"), now)
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}
	raw, err := base64.URLEncoding.DecodeString(string(tok))
	if err != nil {
		t.Fatalf("decode token: %v", err)
	}
	raw[len(raw)-1] ^= 0x80
	bad := base64.URLEncoding.EncodeToString(raw)
	if _, err := Decrypt(key, []byte(bad), now); !errors.Is(err, ErrInvalidToken) {
		t.Fatalf("tampered HMAC decrypt err = %v, want ErrInvalidToken", err)
	}
}

// TestFernetWrongKeyFails encrypts with one key and tries to decrypt with
// another. Must fail with ErrInvalidToken.
func TestFernetWrongKeyFails(t *testing.T) {
	keyA := mustKey(t, "ZORv1Peaqz48dbQzzv9LmVu2qvOE5TPvxN8Qr0k7pZw=")
	keyB := mustKey(t, "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
	now := time.Unix(1_700_000_000, 0)
	tok, err := Encrypt(keyA, []byte("payload"), now)
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}
	if _, err := Decrypt(keyB, []byte(tok), now); !errors.Is(err, ErrInvalidToken) {
		t.Fatalf("wrong-key decrypt err = %v, want ErrInvalidToken", err)
	}
}

// TestFernetBadBase64Fails confirms non-base64 input is rejected.
func TestFernetBadBase64Fails(t *testing.T) {
	key := mustKey(t, "ZORv1Peaqz48dbQzzv9LmVu2qvOE5TPvxN8Qr0k7pZw=")
	if _, err := Decrypt(key, []byte("!!! not base64 !!!"), time.Now()); !errors.Is(err, ErrInvalidToken) {
		t.Fatalf("bad base64 err = %v, want ErrInvalidToken", err)
	}
}

// TestFernetBadVersionFails crafts a token with the wrong version byte and
// expects ErrInvalidToken (no HMAC mismatch leak).
func TestFernetBadVersionFails(t *testing.T) {
	key := mustKey(t, "ZORv1Peaqz48dbQzzv9LmVu2qvOE5TPvxN8Qr0k7pZw=")
	now := time.Unix(1_700_000_000, 0)
	tok, err := Encrypt(key, []byte("hi"), now)
	if err != nil {
		t.Fatalf("encrypt: %v", err)
	}
	raw, err := base64.URLEncoding.DecodeString(string(tok))
	if err != nil {
		t.Fatalf("decode: %v", err)
	}
	raw[0] = 0x81
	bad := base64.URLEncoding.EncodeToString(raw)
	if _, err := Decrypt(key, []byte(bad), now); !errors.Is(err, ErrInvalidToken) {
		t.Fatalf("bad version err = %v, want ErrInvalidToken", err)
	}
}

// TestFernetTruncatedFails confirms a token shorter than the floor is
// rejected with ErrInvalidToken (length check fires before HMAC).
func TestFernetTruncatedFails(t *testing.T) {
	key := mustKey(t, "ZORv1Peaqz48dbQzzv9LmVu2qvOE5TPvxN8Qr0k7pZw=")
	if _, err := Decrypt(key, []byte("Z"), time.Now()); !errors.Is(err, ErrInvalidToken) {
		t.Fatalf("truncated err = %v, want ErrInvalidToken", err)
	}
}

// TestFernetBadKeyLengthFails ensures invalid key shapes fail loudly at
// encrypt-time (cryptography raises ValueError there too).
func TestFernetBadKeyLengthFails(t *testing.T) {
	now := time.Now()
	if _, err := Encrypt([]byte("short"), []byte("x"), now); err == nil {
		t.Fatal("expected error for short key, got nil")
	}
	if _, err := Decrypt([]byte("short"), []byte("Z"), now); err == nil {
		t.Fatal("expected error for short key, got nil")
	}
}

// TestPKCS7PadUnpad exercises the padding helpers directly.
func TestPKCS7PadUnpad(t *testing.T) {
	cases := []int{0, 1, 15, 16, 17, 31, 32, 100}
	for _, n := range cases {
		in := bytes.Repeat([]byte{0xAB}, n)
		padded := pkcs7Pad(in, 16)
		if len(padded)%16 != 0 {
			t.Fatalf("n=%d: padded len %d not a multiple of 16", n, len(padded))
		}
		got, err := pkcs7Unpad(padded, 16)
		if err != nil {
			t.Fatalf("n=%d: unpad err: %v", n, err)
		}
		if !bytes.Equal(got, in) {
			t.Fatalf("n=%d: round-trip mismatch", n)
		}
	}
}

// TestPKCS7UnpadRejectsBad asserts the malformed-pad cases return ErrInvalidToken.
func TestPKCS7UnpadRejectsBad(t *testing.T) {
	cases := []struct {
		name string
		in   []byte
	}{
		{"empty", nil},
		{"not block aligned", []byte{0x01, 0x02}},
		{"zero pad byte", []byte{0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x00}},
		{"pad byte too large", []byte{0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x11}},
		{"pad bytes disagree", []byte{0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x41, 0x03, 0x02}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			if _, err := pkcs7Unpad(tc.in, 16); !errors.Is(err, ErrInvalidToken) {
				t.Fatalf("got err %v, want ErrInvalidToken", err)
			}
		})
	}
}

// mustKey returns the raw 32 bytes for a hardcoded base64 test key, or fails
// the test if the fixture is malformed. Surfaces a typo in the test fixture
// instead of silently breaking later assertions. The 44-char Fernet key can
// be supplied with or without trailing padding — we normalize to the URL-safe
// base64 form (no padding) the fernet package expects.
func mustKey(t *testing.T, s string) []byte {
	t.Helper()
	raw, err := decodeKey([]byte(s))
	if err != nil {
		t.Fatalf("test key %q: %v", s, err)
	}
	return raw
}
