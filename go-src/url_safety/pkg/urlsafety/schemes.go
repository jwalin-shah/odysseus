package urlsafety

import "strings"

// AllowedSchemes is the whitelist of URL schemes the validator accepts.
// Anything else (file://, javascript:, data:, vbscript:, gopher://, ftp://,
// etc.) is rejected at the very first check.
//
// This mirrors src/url_safety.py's ALLOWED_SCHEMES tuple exactly.
var AllowedSchemes = []string{"http", "https"}

// IsAllowedScheme reports whether scheme (case-insensitive) is in the
// whitelist. An empty string is NOT allowed — see ParseURL for the error
// path that handles "(none)".
func IsAllowedScheme(scheme string) bool {
	for _, s := range AllowedSchemes {
		if strings.EqualFold(scheme, s) {
			return true
		}
	}
	return false
}

// NormalizeScheme lowercases the scheme so case-mixed inputs like
// "HTTP://example.com" pass the whitelist check. Returns the empty string
// for an empty input so callers can distinguish "no scheme" from "scheme
// normalized".
func NormalizeScheme(scheme string) string {
	return strings.ToLower(strings.TrimSpace(scheme))
}
