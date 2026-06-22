# settings_scrub (Go port)

Go port of [`src/settings_scrub.py`](../../src/settings_scrub.py). The
Python module is a small, stdlib-only secret-redaction helper used by the
auth-exempt `/api/auth/settings` endpoint: the frontend (and the
pre-login page) read it for keybinds + TTS prefs, so non-admin and
unauthenticated callers must receive a *scrubbed* copy. Secrets (provider
API keys, IMAP/SMTP passwords, OAuth tokens) must NOT leak to them. This
is load-bearing when the app is reachable over a Cloudflare tunnel /
reverse proxy.

The scrub is deep — it recurses through nested dicts/lists — and keyed on
secret-shaped names. The regex, allow-list, and exact-name set from the
Python source are pinned verbatim so the port is behaviorally equivalent.

## Layout

```
go-src/settings_scrub/
  go.mod                              # module github.com/odysseus/settings_scrub, go 1.22
  README.md
  pkg/settingsscrub/
    config.go                         # secret key patterns, allow-list, sensitive-name set,
                                      #   and the two compiled camelCase regexes
    scrub.go                          # canonicalKeyName, IsSecretKey, scrubValue,
                                      #   ScrubSettings, JSONScrubSettings
    json.go                           # thin encoding/json helper so scrub.go stays focused
    settingsscrub_test.go             # table-driven coverage of the full public API
  cmd/settingsscrub-demo/
    main.go                           # --json / --secret / --probe / --help demo CLI
```

## Mapping (Python → Go)

| Python (`src/settings_scrub.py`)             | Go (`settingsscrub`)                                   |
| -------------------------------------------- | ------------------------------------------------------ |
| `_SECRET_KEY_PATTERNS`                       | `secretKeyPatterns` (package var)                      |
| `_SECRET_KEY_ALLOW`                          | `secretKeyAllow` (package var, `map[string]struct{}`)  |
| `_SENSITIVE_KEY_EXACT`                       | `sensitiveKeyExact` (package var, `map[string]struct{}`) |
| `_canonical_key_name(name)`                  | `canonicalKeyName(name)` (unexported)                  |
| `is_secret_key(name)`                        | `IsSecretKey(name)` (exported)                         |
| `_scrub_value(key, value)`                   | `scrubValue(key, value)` (unexported)                  |
| `scrub_settings(settings)`                   | `ScrubSettings(map[string]any) map[string]any`         |
| *(no JSON helper in Python)*                 | `JSONScrubSettings([]byte) map[string]any`             |

The Python module returns `dict` and recurses through arbitrary nested
containers; the Go port works on `map[string]any` / `[]any` — the shape
that `encoding/json` produces for an arbitrary JSON object. Callers that
hold the settings as raw JSON bytes can use `JSONScrubSettings` directly.

## Public API

```go
import contextscrub "github.com/odysseus/settings_scrub/pkg/settingsscrub"

// --- Predicate (mirrors `is_secret_key`) ---
if contextscrub.IsSecretKey("openai_api_key") { /* redacted */ }
if !contextscrub.IsSecretKey("google_pse_cx")   { /* safe to expose */ }

// --- Scrub a parsed settings map ---
out := contextscrub.ScrubSettings(map[string]any{
    "openai_api_key": "sk-12345",
    "theme":          "dark",
})
// out["openai_api_key"] == ""
// out["theme"]          == "dark"

// --- Scrub a raw JSON body (convenience for /api/auth/settings) ---
body := []byte(`{"openai_api_key":"sk-12345","theme":"dark"}`)
out  := contextscrub.JSONScrubSettings(body)
// Malformed / empty / non-object input yields an empty (non-nil) map.
```

## Behavioural parity

The Python test suite (`tests/test_settings_scrub.py`) is translated
verbatim into `settingsscrub_test.go`. Each scenario in the Python suite
has a matching test in Go:

| Python test                                  | Go test                                            |
| -------------------------------------------- | -------------------------------------------------- |
| `test_top_level_secrets_blanked`             | `TestScrubSettingsTopLevelSecretsBlank`            |
| `test_broadened_patterns_blanked`            | `TestScrubSettingsBroadenedPatternsBlank`          |
| `test_nested_secret_blanked`                 | `TestScrubSettingsNestedSecret`                    |
| `test_secret_in_list_of_dicts_blanked`       | `TestScrubSettingsSecretInListOfDicts`             |
| `test_non_secret_keys_preserved`             | `TestScrubSettingsNonSecretKeysPreserved`          |
| `test_google_pse_cx_is_public`               | `TestScrubSettingsGooglePSECXIsPublic`             |
| `test_webhook_integration_handle_blanked`    | `TestScrubSettingsWebhookIntegrationHandleBlank`   |
| `test_empty_and_nonstring_secret_values_untouched` | `TestScrubSettingsEmptyAndNonStringSecretValuesUntouched` |
| `test_exact_name_matches`                    | `TestScrubSettingsExactNameMatches`                |
| `test_camel_case_secret_keys_blanked`        | `TestScrubSettingsCamelCaseSecretKeysBlank`        |
| `test_non_object_settings_return_empty_mapping` | `TestScrubSettingsNonDictInputReturnsEmpty`      |

Plus extra coverage for `IsSecretKey` (allow-list bypass, exact sensitive
match, suffix pattern + bare-name match), `canonicalKeyName` (snake/camel/
kebab normalisation), `JSONScrubSettings` (empty body, malformed JSON,
top-level non-object, JSON null, round-trip), and an
input-mutation guarantee.

## Running tests

```bash
cd go-src/settings_scrub
go build ./...
go vet ./...
go test ./...
```

All tests use only `testing`, `bytes`, `encoding/json`, and `reflect` —
no fixtures, no network, no temp files.

## Demo CLI

```bash
cd go-src/settings_scrub
go build -o /tmp/settingsscrub-demo ./cmd/settingsscrub-demo

# Scrub a JSON document.
echo '{"openai_api_key":"sk-K","theme":"dark","email_account":{"smtp_password":"SECRET"}}' \
  | /tmp/settingsscrub-demo --json @-

# Scrub a single key=value pair.
/tmp/settingsscrub-demo --secret openai_api_key=sk-LIVE-12345

# Probe the predicate alone.
/tmp/settingsscrub-demo --probe apiKey
/tmp/settingsscrub-demo --probe google_pse_cx

# Help.
/tmp/settingsscrub-demo --help
```

The CLI exits 0 on a successful scrub (or `--help`), 2 on missing/invalid
arguments.

## Port notes

- **Single-pass vs two-pass regex replacement.** Go's `regexp` package
  silently drops the second back-reference when the template uses the
  bare `$1_$2` form — the `_$2` portion is folded into the literal
  `"_$2"` and the underscore never gets emitted. The port uses the
  braced form `${1}_${2}` in both replacements so the camelCase splitter
  matches the Python source exactly. This was caught and fixed before
  the test suite went green; it is the only behavioural surprise in the
  port.

- **JSON helper.** `JSONScrubSettings` is a small convenience that
  doesn't exist in the Python source (Python callers do
  `scrub_settings(json.loads(body))`). It is added because the typical
  Go caller has the body as `[]byte` rather than a parsed map, and the
  empty / malformed / non-object fallbacks match the spirit of
  `scrub_settings`'s "non-dict returns empty mapping" rule.

- **No input mutation.** The Python `dict` comprehension in
  `scrub_settings` produces a fresh dict. The Go port uses
  `make(map[string]any, len(settings))` so the input is never modified
  (covered by `TestScrubSettingsDoesNotMutateInput`).

- **Empty / non-string values are preserved.** A `0` int, `false` bool,
  empty string, or `nil` under a secret-shaped key is left untouched —
  only non-empty *string* values are blanked. This matches the Python
  source's `isinstance(value, str) and value` guard exactly.

- **String-only pattern matching.** The Python `_scrub_value` only ever
  touches values that are `dict`/`list`/`str` (because that's what
  `json.loads` produces). The Go port mirrors this by only recursing
  into `map[string]any` / `[]any` and only blanking `string` leaves.
  Other map types (`map[string]string`, `map[string]int`) and typed
  slices are passed through unchanged — if a caller needs deeper
  recursion over those, they should re-decode via `encoding/json`
  first.