package aiinteraction

import "encoding/base64"

// base64Decode is a tiny shim around encoding/base64 so callers don't
// have to import the package themselves. The Python source uses
// `base64.b64decode` directly; this returns the same output.
func base64Decode(s string) ([]byte, error) {
	return base64.StdEncoding.DecodeString(s)
}
