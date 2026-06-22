package urlsecurity

import (
	"strings"
)

// IsPublicHTTPURL reports whether rawURL is a non-empty, well-formed
// http(s) URL whose hostname resolves to one or more public IP
// addresses. Mirrors `is_public_http_url` in src/url_security.py.
//
// It does not check length; use ValidatePublicHTTPURL for the strict
// path that enforces the 2048-char cap and surfaces rejection as an
// error.
func IsPublicHTTPURL(rawURL string) bool {
	v := Classify(rawURL)
	return v.Reason == "ok"
}

// ValidatePublicHTTPURL is the strict validator. It returns the
// trimmed URL on success, or an error explaining why the URL was
// rejected. Mirrors `validate_public_http_url` in
// src/url_security.py.
//
// maxLength <= 0 means "use DefaultMaxLength".
func ValidatePublicHTTPURL(rawURL string, maxLength int) (string, error) {
	if maxLength <= 0 {
		maxLength = DefaultMaxLength
	}
	cleaned := strings.TrimSpace(rawURL)
	if len(cleaned) > maxLength {
		return "", errTooLong
	}
	if !IsPublicHTTPURL(cleaned) {
		return "", errNotPublic
	}
	return cleaned, nil
}
