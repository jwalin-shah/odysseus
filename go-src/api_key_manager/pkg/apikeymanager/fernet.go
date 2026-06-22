package apikeymanager

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
)

// fernetVersion is the version byte every Fernet token starts with. The
// current Fernet spec (https://github.com/fernet/spec) only defines v0x80.
const fernetVersion byte = 0x80

// fernetMinTokenLen is the size of the smallest legal Fernet token after
// base64url decoding: 1 (version) + 8 (timestamp) + 16 (IV) + 16 (at least
// one block of ciphertext, AES block = 16 bytes — empty plaintext still
// pads to one block) + 32 (HMAC-SHA256) = 73 bytes.
const fernetMinTokenLen = 73

// fernetKeyLen is the size of the raw (pre-base64) Fernet key in bytes. The
// key is signing-key (16) || encryption-key (16).
const fernetKeyLen = 32

// splitFernetKey returns the (signing key, encryption key) halves of a
// 32-byte raw Fernet key.
func splitFernetKey(raw []byte) (signing, encryption []byte) {
	return raw[:16], raw[16:]
}

// encodeFernetKey takes the 32 raw bytes of a Fernet key and returns the
// 44-character url-safe base64 string. This is the format Python's
// Fernet.generate_key() emits and the format Fernet() expects on
// construction.
//
// The Python helper writes the raw base64 string to .key; this port writes
// the same form so a file written by the Go port can be loaded by the
// Python module and vice-versa (the wire-format is identical).
func encodeFernetKey(raw []byte) string {
	return base64.URLEncoding.EncodeToString(raw)
}

// decodeFernetKey parses a Fernet key as produced by Python's
// Fernet.generate_key() — a 44-character url-safe base64 string that
// decodes to exactly 32 raw bytes (signing-key || encryption-key).
//
// Python's Fernet accepts both the 44-char padded form ("=" sometimes
// present) and the unpadded form; the URL-safe base64 decoder used here
// (RawURLEncoding / URLEncoding) handles both. Returns the 32 raw bytes
// or an error that wraps ErrInvalidToken when the key is malformed.
func decodeFernetKey(encoded string) ([]byte, error) {
	if encoded == "" {
		return nil, ErrInvalidToken
	}
	// Try padded first (the typical Fernet.generate_key() output), then
	// raw unpadded. The two decoders share the same alphabet so we can
	// switch by trial and pick the one that yields fernetKeyLen bytes.
	if raw, err := base64.URLEncoding.DecodeString(encoded); err == nil && len(raw) == fernetKeyLen {
		return raw, nil
	}
	if raw, err := base64.RawURLEncoding.DecodeString(encoded); err == nil && len(raw) == fernetKeyLen {
		return raw, nil
	}
	return nil, ErrInvalidToken
}

// fernetEncode encrypts plaintext under a 32-byte raw Fernet key and
// returns the URL-safe base64 token. Mirrors Python's
// cryptography.fernet.Fernet.encrypt. The token layout (pre-base64) is:
//
//	Version (1) || Timestamp (8) || IV (16) || Ciphertext (N*16) || HMAC (32)
//
// Timestamp is the current time in seconds since epoch (the Fernet spec
// does not require it to be embedded in the key, so we always emit "now"
// — Python's Fernet.encrypt uses the same convention).
func fernetEncode(rawKey, plaintext []byte) (string, error) {
	if len(rawKey) != fernetKeyLen {
		return "", ErrInvalidToken
	}
	signingKey, encryptionKey := splitFernetKey(rawKey)

	iv := make([]byte, aes.BlockSize)
	if _, err := randRead(iv); err != nil {
		return "", err
	}

	ts := make([]byte, 8)
	binary.BigEndian.PutUint64(ts, nowSeconds())

	// AES-128-CBC with PKCS#7 padding.
	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return "", err
	}
	padded := pkcs7Pad(plaintext, block.BlockSize())
	ciphertext := make([]byte, len(padded))
	cbcEnc := cipher.NewCBCEncrypter(block, iv)
	cbcEnc.CryptBlocks(ciphertext, padded)

	// Pre-base64 token bytes: version || timestamp || iv || ciphertext.
	tokenBytes := make([]byte, 0, 1+8+16+len(ciphertext)+sha256.Size)
	tokenBytes = append(tokenBytes, fernetVersion)
	tokenBytes = append(tokenBytes, ts...)
	tokenBytes = append(tokenBytes, iv...)
	tokenBytes = append(tokenBytes, ciphertext...)

	// HMAC-SHA256 over the pre-base64 token bytes (everything except the
	// trailing 32-byte HMAC slot). The Fernet spec is explicit: HMAC input
	// is the pre-base64 bytes, not the base64 string.
	mac := hmac.New(sha256.New, signingKey)
	mac.Write(tokenBytes)
	tokenBytes = append(tokenBytes, mac.Sum(nil)...)

	return base64.URLEncoding.EncodeToString(tokenBytes), nil
}

// fernetDecode reverses fernetEncode. Returns ErrInvalidToken (wrapped)
// when the token is malformed, has the wrong version, has a stale or
// truncated structure, or fails the HMAC check.
func fernetDecode(rawKey []byte, token string) ([]byte, error) {
	if len(rawKey) != fernetKeyLen {
		return nil, ErrInvalidToken
	}
	signingKey, encryptionKey := splitFernetKey(rawKey)

	raw, err := base64.URLEncoding.DecodeString(token)
	if err != nil {
		// Try raw (no padding) too — the spec allows unpadded tokens.
		if raw2, err2 := base64.RawURLEncoding.DecodeString(token); err2 == nil {
			raw = raw2
		} else {
			return nil, ErrInvalidToken
		}
	}
	if len(raw) < fernetMinTokenLen {
		return nil, ErrInvalidToken
	}
	if raw[0] != fernetVersion {
		return nil, ErrInvalidToken
	}

	// Split off the HMAC (last 32 bytes) and the payload.
	hmacStart := len(raw) - sha256.Size
	payload := raw[:hmacStart]
	mac := hmac.New(sha256.New, signingKey)
	mac.Write(payload)
	if !hmac.Equal(mac.Sum(nil), raw[hmacStart:]) {
		return nil, ErrInvalidToken
	}

	// version (1) + timestamp (8) + iv (16) = 25 header bytes.
	const headerLen = 1 + 8 + 16
	if len(payload) < headerLen {
		return nil, ErrInvalidToken
	}
	iv := payload[1+8 : headerLen]
	ciphertext := payload[headerLen:]

	block, err := aes.NewCipher(encryptionKey)
	if err != nil {
		return nil, ErrInvalidToken
	}
	if len(ciphertext)%block.BlockSize() != 0 {
		return nil, ErrInvalidToken
	}
	plain := make([]byte, len(ciphertext))
	cbcDec := cipher.NewCBCDecrypter(block, iv)
	cbcDec.CryptBlocks(plain, ciphertext)

	out, err := pkcs7Unpad(plain, block.BlockSize())
	if err != nil {
		return nil, ErrInvalidToken
	}
	return out, nil
}
