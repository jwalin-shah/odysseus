package settingsscrub

import (
	"strings"
)

// canonicalKeyName normalises common JS-style key names so secret matching
// is style-agnostic. The Python source's `_canonical_key_name` does:
//
//	n = (name or "").replace("-", "_")
//	n = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", n)
//	n = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", n)
//	return n.lower()
//
// The two-pass regex splits a camelCase identifier on the lower→upper
// boundary so "apiKey" → "api_Key" → "api_key" and "accessToken" →
// "access_token". Identifiers that are already snake_case are untouched.
// Dashes are converted to underscores so "api-key" and "api_key" produce
// the same canonical form.
//
// A nil or empty input is preserved as the empty string. The Python
// source's `(name or "")` is equivalent because the bool coercion treats
// empty / None as falsy; this function just short-circuits to "".
func canonicalKeyName(name string) string {
	if name == "" {
		return ""
	}
	n := strings.ReplaceAll(name, "-", "_")
	n = camelBoundary1.ReplaceAllString(n, "${1}_${2}")
	n = camelBoundary2.ReplaceAllString(n, "${1}_${2}")
	return strings.ToLower(n)
}

// IsSecretKey reports whether the given key name (in any common JS-style
// form — snake_case, camelCase, kebab-case) refers to a secret-shaped
// value that the scrubber must redact.
//
// The match order mirrors src/settings_scrub.py:
//
//  1. If the canonicalised key is in the allow-list (e.g. "google_pse_cx"),
//     it is NOT a secret.
//  2. If the canonicalised key is in the exact sensitive-name set (e.g.
//     "reminder_webhook_integration_id"), it IS treated as a secret even
//     though it isn't secret-shaped.
//  3. Otherwise the key is secret if its canonical form ends with one of
//     the configured patterns OR equals a pattern stripped of its leading
//     underscore (so "password", "token", "secret", "apikey", "key" all
//     match exactly).
//
// The function is exported because the Python source's `is_secret_key`
// is public; both the scrubber and tests use it.
func IsSecretKey(name string) bool {
	n := canonicalKeyName(name)
	if _, ok := secretKeyAllow[n]; ok {
		return false
	}
	if _, ok := sensitiveKeyExact[n]; ok {
		return true
	}
	for _, p := range secretKeyPatterns {
		if n == strings.TrimPrefix(p, "_") {
			return true
		}
		if strings.HasSuffix(n, p) {
			return true
		}
	}
	return false
}

// scrubValue masks secret-shaped leaves and recurses into nested maps and
// slices so a secret stored under a non-secret parent key (e.g.
//
//	{"email_account": {"smtp_password": "..."}}
//
// ) is still blanked. The Python source's `_scrub_value(key, value)` is
// translated 1:1:
//
//   - if value is a map[string]any, recurse into each entry. When the entry
//     key is secret-shaped AND the entry value is a non-empty string, the
//     value is replaced with "" (presence is preserved). Otherwise the
//     value is recursed through (so nested maps / slices are still walked).
//   - if value is a []any, recurse into each item. The OUTER key is passed
//     down; for items that are dicts the inner dict's own keys will be
//     re-checked against the secret patterns via the map branch above.
//   - if the key is secret-shaped AND the value is a non-empty string,
//     return "".
//   - any other type (int, bool, nil, empty string) is returned unchanged.
//
// In Go the "dict" branch is `map[string]any` and the "list" branch is
// `[]any`. Other map types (map[string]string, map[string]int, etc.) and
// typed slices are returned unchanged because the Python source's
// `_scrub_value` is only ever called with values that have been JSON-
// decoded into the standard `dict` / `list` containers.
func scrubValue(key string, value any) any {
	switch v := value.(type) {
	case map[string]any:
		out := make(map[string]any, len(v))
		for k, item := range v {
			if IsSecretKey(k) {
				if s, ok := item.(string); ok && s != "" {
					out[k] = ""
					continue
				}
			}
			out[k] = scrubValue(k, item)
		}
		return out
	case []any:
		out := make([]any, len(v))
		for i, item := range v {
			out[i] = scrubValue(key, item)
		}
		return out
	default:
		if IsSecretKey(key) {
			if s, ok := value.(string); ok && s != "" {
				return ""
			}
		}
		return value
	}
}

// ScrubSettings returns a copy of settings with secret-shaped values masked
// (deep). It mirrors src/settings_scrub.scrub_settings:
//
//	if not isinstance(settings, dict):
//	    return {}
//	return {k: _scrub_value(k, v) for k, v in (settings or {}).items()}
//
// A nil or non-map input returns an empty (but non-nil) map[string]any so
// callers can JSON-encode the result directly without a nil check.
func ScrubSettings(settings map[string]any) map[string]any {
	out := make(map[string]any, len(settings))
	for k, v := range settings {
		out[k] = scrubValue(k, v)
	}
	return out
}

// JSONScrubSettings is a convenience wrapper for callers that hold the
// incoming settings as a JSON byte slice (the typical shape of the
// /api/auth/settings endpoint). It is the Go equivalent of:
//
//	scrub_settings(json.loads(body))
//
// Behaviour:
//
//   - empty / nil input → empty map;
//   - malformed JSON    → empty map (the scrubber must never block the
//     auth-exempt settings endpoint on a parse error);
//   - top-level JSON is not a map → empty map (matches the Python
//     `isinstance(settings, dict)` check).
//
// The intentional silent fallback to `{}` on parse error matches the
// spirit of the Python source: scrub_settings returns an empty mapping
// for non-dict input and never raises.
func JSONScrubSettings(body []byte) map[string]any {
	if len(body) == 0 {
		return map[string]any{}
	}
	var parsed map[string]any
	if err := jsonUnmarshal(body, &parsed); err != nil {
		return map[string]any{}
	}
	if parsed == nil {
		return map[string]any{}
	}
	return ScrubSettings(parsed)
}
