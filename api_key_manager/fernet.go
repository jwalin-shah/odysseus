// Fernet-style symmetric authenticated encryption (encrypt/decrypt only).
//
// Format follows the Fernet spec v0x80:
//
//	Version (1 byte, 0x80) || Timestamp (8 bytes, big-endian, unix seconds)
//	|| IV (16 bytes) || Ciphertext (PKCS#7-padded) || HMAC-SHA256 (32 bytes)
//
// All wrapped in URL-safe base64 without padding. Authentication uses HMAC-SHA256
// keyed with the second half of the supplied key (key[32:]).
//
// This is intentionally a minimal, decrypt-only-compatible subset — no key
// rotation, no MultiFernet. The cryptography library's Fernet is the reference.
package api_key_manager

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"time"
)

// Sentinel error returned for any decrypt-time validation failure (bad base64,
// wrong length, bad HMAC, bad PKCS#7 padding). Mirrors cryptography's
// InvalidToken — callers should treat it as "do not use this value".
var ErrInvalidToken = errors.New("api_key_manager: invalid fernet token")

const (
	fernetVersion   byte = 0x80
	fernetIVLen          = 16
	fernetHMACLen        = 32
	fernetKeyLen         = 32 // raw key bytes (before base64)
	fernetKeyB64Len      = 44 // URL-safe base64 of 32 bytes, no padding
	// minTokenLen = version(1) + timestamp(8) + iv(16) + hmac(32) + at least one
	// block of ciphertext + 1 byte of PKCS#7 padding. AES block size is 16,
	// so ciphertext+padding is >= 16 bytes. Use 57 as the floor.
	fernetMinTokenLen = 1 + 8 + fernetIVLen + 16 + fernetHMACLen
)

// decodeKey accepts the Fernet-style URL-safe-base64-encoded 32-byte key and
// returns the raw bytes. A raw 32-byte slice is also accepted so internal
// callers can pass raw bytes if they already have them. URL-safe base64 with
// or without trailing padding is accepted — Python cryptography.Fernet keys
// are emitted with one trailing '=' (e.g. "ZORv...pZw=").
func decodeKey(key []byte) ([]byte, error) {
	if len(key) == fernetKeyLen {
		return key, nil
	}
	// Accept both padded (45 chars) and unpadded (44 chars) URL-safe base64.
	if len(key) != fernetKeyB64Len && len(key) != fernetKeyB64Len+1 {
		return nil, fmt.Errorf("fernet: key must be 32 raw bytes or 44 base64 chars, got %d", len(key))
	}
	decoded, err := base64.URLEncoding.DecodeString(string(key))
	if err != nil {
		return nil, fmt.Errorf("fernet: key not valid base64: %w", err)
	}
	if len(decoded) != fernetKeyLen {
		return nil, fmt.Errorf("fernet: decoded key length %d, want %d", len(decoded), fernetKeyLen)
	}
	return decoded, nil
}

// GenerateKey returns a fresh Fernet key as a URL-safe-base64 string (44
// chars, no padding). Mirrors cryptography.fernet.Fernet.generate_key.
func GenerateKey() ([]byte, error) {
	raw := make([]byte, fernetKeyLen)
	if _, err := io.ReadFull(rand.Reader, raw); err != nil {
		return nil, fmt.Errorf("fernet: read random: %w", err)
	}
	out := make([]byte, base64.URLEncoding.EncodedLen(fernetKeyLen))
	base64.URLEncoding.Encode(out, raw)
	return out, nil
}

// Encrypt seals plaintext under the given Fernet key and returns the URL-safe
// base64 (no padding) token string. The timestamp is taken from the wall clock
// at call time.
func Encrypt(key []byte, plaintext []byte, now time.Time) ([]byte, error) {
	raw, err := decodeKey(key)
	if err != nil {
		return nil, err
	}
	signingKey := raw[:16] // first 16 bytes = signing/HMAC key
	encKey := raw[16:32]   // last 16 bytes = AES-CBC key

	iv := make([]byte, fernetIVLen)
	if _, err := io.ReadFull(rand.Reader, iv); err != nil {
		return nil, fmt.Errorf("fernet: read iv: %w", err)
	}

	block, err := aes.NewCipher(encKey)
	if err != nil {
		// aes.NewCipher only errors on invalid key sizes; decodeKey already
		// guarantees 32 bytes, so this is unreachable but kept for safety.
		return nil, fmt.Errorf("fernet: aes.NewCipher: %w", err)
	}
	padded := pkcs7Pad(plaintext, aes.BlockSize)
	ciphertext := make([]byte, len(padded))
	cipher.NewCBCEncrypter(block, iv).CryptBlocks(ciphertext, padded)

	token := make([]byte, 0, 1+8+fernetIVLen+len(ciphertext)+fernetHMACLen)
	token = append(token, fernetVersion)
	ts := make([]byte, 8)
	binary.BigEndian.PutUint64(ts, uint64(now.Unix()))
	token = append(token, ts...)
	token = append(token, iv...)
	token = append(token, ciphertext...)

	mac := hmac.New(sha256.New, signingKey)
	mac.Write(token)
	token = append(token, mac.Sum(nil)...)

	out := make([]byte, base64.URLEncoding.EncodedLen(len(token)))
	base64.URLEncoding.Encode(out, token)
	return out, nil
}

// Decrypt validates and unseals a Fernet token. Any failure (bad base64,
// wrong version, wrong length, HMAC mismatch, bad PKCS#7 padding) returns
// ErrInvalidToken so callers cannot distinguish failure modes by error
// type — matching cryptography.fernet.InvalidToken behaviour.
func Decrypt(key []byte, token []byte, now time.Time) ([]byte, error) {
	raw, err := decodeKey(key)
	if err != nil {
		return nil, ErrInvalidToken
	}
	signingKey := raw[:16]

	decoded, err := base64.URLEncoding.DecodeString(string(token))
	if err != nil {
		return nil, ErrInvalidToken
	}
	if len(decoded) < fernetMinTokenLen {
		return nil, ErrInvalidToken
	}
	if decoded[0] != fernetVersion {
		return nil, ErrInvalidToken
	}

	bodyEnd := len(decoded) - fernetHMACLen
	body := decoded[:bodyEnd]
	gotMAC := decoded[bodyEnd:]

	mac := hmac.New(sha256.New, signingKey)
	mac.Write(body)
	wantMAC := mac.Sum(nil)
	if !hmac.Equal(gotMAC, wantMAC) {
		return nil, ErrInvalidToken
	}

	// body = version(1) || timestamp(8) || iv(16) || ciphertext(...)
	iv := body[9 : 9+fernetIVLen]
	ciphertext := body[9+fernetIVLen:]
	if len(ciphertext)%aes.BlockSize != 0 {
		return nil, ErrInvalidToken
	}

	block, err := aes.NewCipher(raw[16:32])
	if err != nil {
		return nil, ErrInvalidToken
	}
	plain := make([]byte, len(ciphertext))
	cipher.NewCBCDecrypter(block, iv).CryptBlocks(plain, ciphertext)

	unpadded, err := pkcs7Unpad(plain, aes.BlockSize)
	if err != nil {
		return nil, ErrInvalidToken
	}

	// Python's Fernet.decrypt does not enforce a TTL — round-trips stay
	// deterministic for tests with frozen clocks. Accept `now` for
	// signature symmetry but do not use it.
	_ = now
	return unpadded, nil
}

// pkcs7Pad appends PKCS#7 padding so the result is a multiple of blockSize.
// blockSize must be > 0 and <= 255 (the maximum one-byte pad value).
func pkcs7Pad(in []byte, blockSize int) []byte {
	padLen := blockSize - (len(in) % blockSize)
	padding := make([]byte, padLen)
	for i := range padding {
		padding[i] = byte(padLen)
	}
	return append(in, padding...)
}

// pkcs7Unpad validates and strips PKCS#7 padding. Returns ErrInvalidToken on
// any malformed padding (wrong length, out-of-range pad byte, or padding
// bytes that don't all match).
func pkcs7Unpad(in []byte, blockSize int) ([]byte, error) {
	if len(in) == 0 || len(in)%blockSize != 0 {
		return nil, ErrInvalidToken
	}
	padLen := int(in[len(in)-1])
	if padLen == 0 || padLen > blockSize || padLen > len(in) {
		return nil, ErrInvalidToken
	}
	for i := len(in) - padLen; i < len(in); i++ {
		if in[i] != byte(padLen) {
			return nil, ErrInvalidToken
		}
	}
	return in[:len(in)-padLen], nil
}
