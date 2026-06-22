package secretstorage

import (
	"encoding/base64"
	"errors"
)

// xorStubCipher is the default Cipher shipped with this port. It is a
// deterministic XOR with a per-key mask, encoded as URL-safe base64.
//
// WARNING: xorStubCipher is NOT secure. It is provided so the
// SecretStorage orchestrator logic (round-trip, prefix handling, error
// fallback, idempotency) can be exercised without pulling in a crypto
// dependency. A real deployment must swap in a Fernet-equivalent cipher
// (AES-128-CBC + HMAC-SHA256, URL-safe base64 token framing) via the
// Cipher interface.
//
// The cipher preserves the contract that SecretStorage.Encrypt
// prepends EncryptedPrefix; xorStubCipher itself never emits a value
// that begins with "enc:".
type xorStubCipher struct {
	mask []byte
}

// NewXORStubCipher returns a Cipher seeded from key. The key length is
// not validated here because some tests deliberately use short keys to
// exercise the failure paths; the SecretStorage constructor is the
// enforcement point.
func NewXORStubCipher(key []byte) (Cipher, error) {
	if len(key) == 0 {
		return nil, errEmptyKey
	}
	cp := make([]byte, len(key))
	copy(cp, key)
	return &xorStubCipher{mask: cp}, nil
}

// Encrypt applies a per-byte XOR with the mask (cycling) and returns
// the result as a URL-safe base64 string. The XOR is symmetric so
// Decrypt applies the same transformation.
func (x *xorStubCipher) Encrypt(plaintext string) (string, error) {
	if plaintext == "" {
		return "", nil
	}
	raw := make([]byte, len(plaintext))
	for i := 0; i < len(plaintext); i++ {
		raw[i] = plaintext[i] ^ x.mask[i%len(x.mask)]
	}
	return base64.RawURLEncoding.EncodeToString(raw), nil
}

// Decrypt reverses Encrypt. A token that fails base64 decoding or that
// XORs back to a value beginning with EncryptedPrefix is rejected with
// an error so SecretStorage.Decrypt can apply its empty-string fallback.
func (x *xorStubCipher) Decrypt(token string) (string, error) {
	if token == "" {
		return "", nil
	}
	raw, err := base64.RawURLEncoding.DecodeString(token)
	if err != nil {
		return "", err
	}
	out := make([]byte, len(raw))
	for i := 0; i < len(raw); i++ {
		out[i] = raw[i] ^ x.mask[i%len(x.mask)]
	}
	plain := string(out)
	if hasEncryptedPrefix(plain) {
		// A plain value shouldn't round-trip into another ciphertext-
		// shaped string. Refuse so SecretStorage.Decrypt falls back
		// rather than returning a corrupt prefix.
		return "", errors.New("xorStubCipher: decrypted value still carries enc: prefix")
	}
	return plain, nil
}

// hasEncryptedPrefix reports whether s begins with EncryptedPrefix.
// Extracted so encrypt/decrypt can share the prefix check without
// repeating the literal.
func hasEncryptedPrefix(s string) bool {
	if len(s) < len(EncryptedPrefix) {
		return false
	}
	return s[:len(EncryptedPrefix)] == EncryptedPrefix
}
