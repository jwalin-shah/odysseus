package secretstorage

import (
	"errors"
	"strings"
)

// Encrypt encrypts plaintext using the underlying Cipher and returns a
// string prefixed with EncryptedPrefix. Empty input returns ""; an
// already-prefixed input passes through unchanged so re-encrypting a
// ciphertext is a no-op (the migration is idempotent).
//
// The returned string is always a valid UTF-8 sequence (the cipher
// operates on bytes; the token is URL-safe ASCII).
func (s *SecretStorage) Encrypt(plaintext string) (string, error) {
	if plaintext == "" {
		return "", nil
	}
	if strings.HasPrefix(plaintext, EncryptedPrefix) {
		return plaintext, nil
	}
	token, err := s.cipher.Encrypt(plaintext)
	if err != nil {
		return "", err
	}
	if hasEncryptedPrefix(token) {
		// Should be impossible — Cipher contract forbids it — but if a
		// future implementation violates that contract, refuse rather
		// than emit a value that downstream IsEncrypted checks can't
		// disambiguate.
		return "", errors.New("secretstorage: cipher produced enc:-prefixed token")
	}
	return EncryptedPrefix + token, nil
}

// Decrypt reverses Encrypt. A value without the EncryptedPrefix is
// returned unchanged (legacy row compatibility). A ciphertext token
// that fails to decrypt yields "" — matching the Python module's
// "unconfigured" fallback — and the underlying error is surfaced via
// the second return so callers can log it.
//
// Returning both "" and a non-nil error mirrors the Python behaviour
// (silent fallback) while staying idiomatic Go: errors are values.
func (s *SecretStorage) Decrypt(value string) (string, error) {
	if value == "" {
		return "", nil
	}
	if !strings.HasPrefix(value, EncryptedPrefix) {
		return value, nil
	}
	token := value[len(EncryptedPrefix):]
	plain, err := s.cipher.Decrypt(token)
	if err != nil {
		return "", err
	}
	return plain, nil
}

// IsEncrypted reports whether value is a ciphertext produced by
// Encrypt. Empty strings are not encrypted (the Python helper returns
// False on empty input).
func (s *SecretStorage) IsEncrypted(value string) bool {
	return value != "" && strings.HasPrefix(value, EncryptedPrefix)
}
