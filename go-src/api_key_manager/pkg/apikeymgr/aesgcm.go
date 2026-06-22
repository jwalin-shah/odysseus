package apikeymgr

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"io"
)

// AES-256-GCM authenticated encryption for API keys.
//
// On-disk format:
//
//	base64( nonce(12 bytes) || ciphertext || gcm_tag(16 bytes) )
//
// We chose AES-256-GCM (over a Python Fernet-compatible format) because:
//
//  1. Stdlib-only — no third-party crypto dependency.
//  2. AEAD in one primitive: AES-GCM authenticates the nonce + ciphertext
//     atomically, so a single cipher.NewGCM gives us confidentiality and
//     integrity with no separate HMAC step.
//  3. Random 96-bit nonce per encrypt; collision risk is negligible for the
//     number of keys a single user stores.
//
// The trade-off vs Fernet: Fernet wraps HMAC-SHA256 + AES-CBC, includes a
// version byte and timestamp, and key-rotation primitives. We don't need
// those — the .key file is created on first use and lives forever. A future
// port that needs key rotation can wrap encryptAES with a key-id prefix.

// ErrInvalidToken is returned for any decrypt-time validation failure
// (bad base64, wrong length, bad nonce size, AEAD tag mismatch).
var ErrInvalidToken = fmt.Errorf("apikeymgr: invalid token")

// generateKey returns aesKeyLen random bytes.
func generateKey() ([]byte, error) {
	key := make([]byte, aesKeyLen)
	if _, err := io.ReadFull(rand.Reader, key); err != nil {
		return nil, fmt.Errorf("apikeymgr: read random: %w", err)
	}
	return key, nil
}

// encryptAES seals plaintext under key and returns the URL-safe base64 of
// (nonce || ciphertext || tag).
//
// GCM's Seal appends ciphertext+tag to dst. We copy the random nonce into
// the first bytes of dst so the on-disk layout is nonce(12) || ciphertext
// || tag(16). (All-zero prefix bytes would corrupt the AEAD tag check on
// decrypt.)
func encryptAES(key []byte, plaintext []byte) (string, error) {
	if len(key) != aesKeyLen {
		return "", fmt.Errorf("apikeymgr: key length %d, want %d", len(key), aesKeyLen)
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return "", fmt.Errorf("apikeymgr: aes.NewCipher: %w", err)
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", fmt.Errorf("apikeymgr: cipher.NewGCM: %w", err)
	}
	nonce := make([]byte, gcmNonceLen)
	if _, err := io.ReadFull(rand.Reader, nonce); err != nil {
		return "", fmt.Errorf("apikeymgr: read nonce: %w", err)
	}
	// Pre-size dst to nonce + ciphertext + tag, copy nonce in as the prefix,
	// then Seal appends ct+tag.
	dst := make([]byte, gcmNonceLen, gcmNonceLen+len(plaintext)+gcm.Overhead())
	copy(dst, nonce)
	out := gcm.Seal(dst, nonce, plaintext, nil)
	return base64.URLEncoding.EncodeToString(out), nil
}

// decryptAES unseals a token produced by encryptAES. Any failure
// (bad base64, wrong length, AEAD tag mismatch) returns ErrInvalidToken.
//
// GCM's Open expects (nonce || ciphertext || tag) as a single ciphertext
// argument. The Seal output already has that layout — we just base64-
// decode and pass the whole thing in.
func decryptAES(key []byte, token string) ([]byte, error) {
	if len(key) != aesKeyLen {
		return nil, ErrInvalidToken
	}
	raw, err := base64.URLEncoding.DecodeString(token)
	if err != nil {
		return nil, ErrInvalidToken
	}
	if len(raw) < gcmNonceLen {
		return nil, ErrInvalidToken
	}
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, ErrInvalidToken
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, ErrInvalidToken
	}
	nonce := raw[:gcmNonceLen]
	ciphertext := raw[gcmNonceLen:]
	plain, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		return nil, ErrInvalidToken
	}
	return plain, nil
}
