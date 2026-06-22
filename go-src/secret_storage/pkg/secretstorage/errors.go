package secretstorage

import "errors"

// Sentinel errors. Callers use errors.Is to distinguish configuration
// failures (nil backend / nil cipher) from runtime failures (corrupt
// token, missing key). The Python module swallows decrypt failures and
// returns ""; this port preserves that behaviour at the Decrypt level
// but exposes the underlying error via Cipher.Decrypt so callers that
// want strict semantics can opt in.
var (
	errNilBackend = errors.New("secretstorage: KeyBackend is nil")
	errNilCipher  = errors.New("secretstorage: Cipher is nil")
	errEmptyKey   = errors.New("secretstorage: key is empty")
	errShortKey   = errors.New("secretstorage: key is shorter than 16 bytes (Fernet minimum)")
	errBackendNil = errors.New("secretstorage: backend returned nil key with no error")
)

// sentinelCipherError is what Decrypt returns when the underlying cipher
// reports a failure and the caller asked for errors-as-values (the
// standard library convention). The Python module returns "" in this
// case; the Go Decrypt does the same and also surfaces a non-nil error
// so callers can choose to log it. Decrypt does not panic; the error
// is wrapped to preserve errors.Is matching across wrappers.
var sentinelCipherError = errors.New("secretstorage: cipher decrypt failed")
