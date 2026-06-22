// Package settingsscrub implements the secret-scrubbing for settings that are
// exposed to non-admin / unauthenticated callers. It is the Go port of
// src/settings_scrub.py.
//
// `/api/auth/settings` is auth-exempt: the frontend (and the pre-login page)
// read it for keybinds + TTS prefs, so non-admin and unauthenticated callers
// receive a *scrubbed* copy. Secrets (provider API keys, IMAP/SMTP passwords,
// OAuth tokens) must NOT leak to them. This is load-bearing when the app is
// reachable over a Cloudflare tunnel / reverse proxy.
//
// The scrubbing is deep — it recurses through nested dicts / lists — and is
// keyed on secret-shaped names. The same regex patterns, allow-list, and
// exact-name match list from the Python source are preserved verbatim so the
// port is behaviorally equivalent.
//
// The package has no external dependencies; it only uses Go stdlib
// (encoding/json for the public JSON helper, regexp for the camelCase
// splitter).
package settingsscrub

import "regexp"

// secretKeyPatterns mirrors `_SECRET_KEY_PATTERNS` in src/settings_scrub.py.
// Any canonicalised key that ends with one of these (or equals the
// non-leading-underscore form, e.g. "password", "token", "key") is treated as
// secret-shaped. The trailing underscore variants are used for prefix
// matching; the leading-underscore variants exist only to keep parity with
// the Python source's tuple.
var secretKeyPatterns = []string{
	"_api_key",
	"_apikey",
	"_password",
	"_passwd",
	"_pass",
	"_pwd",
	"_secret",
	"_client_secret",
	"_token",
	"_access_token",
	"_refresh_token",
	"_credential",
	"_credentials",
	"_key",
}

// secretKeyAllow mirrors `_SECRET_KEY_ALLOW` in src/settings_scrub.py.
// These are public identifiers that LOOK secret-shaped but are explicitly
// safe to expose (so the scrubber must skip them).
var secretKeyAllow = map[string]struct{}{
	"google_pse_cx": {},
}

// sensitiveKeyExact mirrors `_SENSITIVE_KEY_EXACT` in src/settings_scrub.py.
// These keys are NOT secret-shaped but must still be redacted on the
// settings endpoint because they are capability handles for routes that
// can trigger outbound webhook sends.
var sensitiveKeyExact = map[string]struct{}{
	"reminder_webhook_integration_id": {},
}

// camelBoundary1 matches "<char><Upper><lower+>" so the camelCase splitter
// inserts an underscore between the prefix and the start of the next word.
// Example: "apiKey" → "api_Key" (then the second pass below splits "K" / "ey").
//
// Compiled once at init via MustCompile for performance — the patterns are
// constant.
var camelBoundary1 = regexp.MustCompile(`(.)([A-Z][a-z]+)`)

// camelBoundary2 matches "<lower|digit><Upper>" so the second pass inserts
// an underscore between the lowercase/digit prefix and the single uppercase
// letter that starts the next word. Example: "apiKey" → "api_Key" →
// "api_key" after the second pass and lowercasing.
//
// These mirror the two-pass regex applied in `_canonical_key_name` in the
// Python source. Both regexes are pinned here verbatim so behavioural
// parity with src/settings_scrub.py is preserved. The replacement templates
// use Go's `${1}_${2}` braced form rather than `$1_$2` — the bare form
// silently swallows the trailing `$2` into the literal "2" when a character
// follows the first reference, which produced wrong output ("apiKey" →
// "apKey" instead of "api_Key").
var camelBoundary2 = regexp.MustCompile(`([a-z0-9])([A-Z])`)
