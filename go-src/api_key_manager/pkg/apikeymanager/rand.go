package apikeymanager

import (
	"crypto/rand"
	"errors"
)

// errBadPadding is the unexported sentinel returned by pkcs7Unpad for
// malformed padding. fernetDecode folds it into ErrInvalidToken so callers
// see a single sentinel for every "this is not a valid token" condition.
var errBadPadding = errors.New("apikeymanager: bad PKCS#7 padding")

// randRead is an indirection around crypto/rand.Read so tests can substitute
// a deterministic source if needed. Defaults to crypto/rand.Read — same
// randomness quality as Python's os.urandom used by Fernet.generate_key().
func randRead(b []byte) (int, error) {
	return rand.Read(b)
}
