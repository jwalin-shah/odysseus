package apikeymanager

import (
	"errors"
)

// Sentinel errors returned by the Manager. Callers use errors.Is to branch
// on these; the Python module's exception types map as follows:
//
//	cryptography.fernet.InvalidToken -> ErrInvalidToken
//	json.JSONDecodeError            -> ErrCorruptStore
//	os errors (permissions, missing file) are surfaced as stdlib
//	wrapped errors (os.PathError, syscall.Errno, etc.) so callers
//	can keep using errors.Is(err, fs.ErrNotExist) etc.
var (
	// ErrInvalidToken is returned by DecryptAPIKey when the on-disk
	// ciphertext is not a valid Fernet token — wrong version byte,
	// truncated, base64 decode failure, or HMAC mismatch. The Python
	// cryptography.fernet.InvalidToken class maps directly to this
	// sentinel; callers use errors.Is to detect it.
	ErrInvalidToken = errors.New("apikeymanager: invalid Fernet token")

	// ErrCorruptStore is returned when api_keys.json exists but cannot
	// be parsed (JSON decode failure, or it parses to something other
	// than an object). The Python module's _load_raw() logs and
	// returns {} in this case; the Go Manager returns ErrCorruptStore
	// so the caller can branch on it explicitly. Use IsCorruptStore to
	// test.
	ErrCorruptStore = errors.New("apikeymanager: api_keys store is corrupt or wrong-shaped")

	// ErrDataDirEmpty is returned by New when dataDir is empty. Mirrors
	// the Python __init__ which would happily join "" with
	// "api_keys.json" to yield an invalid path; we surface the mistake
	// earlier.
	ErrDataDirEmpty = errors.New("apikeymanager: data dir is empty")

	// ErrEmptyProvider is returned by Save when provider is "". The
	// Python module would happily write an empty key to disk; the Go
	// port refuses so a caller-side bug (e.g. a missing form field)
	// cannot silently drop a stored key.
	ErrEmptyProvider = errors.New("apikeymanager: provider name is empty")
)

// IsCorruptStore reports whether err is or wraps ErrCorruptStore. Convenience
// predicate so callers don't have to import errors in trivial call sites.
func IsCorruptStore(err error) bool {
	return errors.Is(err, ErrCorruptStore)
}
