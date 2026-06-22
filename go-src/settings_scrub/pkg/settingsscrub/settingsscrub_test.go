// Tests for the settingsscrub package. Coverage:
//
//   - IsSecretKey: allow-list, exact sensitive-name set, snake/camel/kebab
//     normalisation, exact bare-name matching (password/token/secret/apikey/key),
//     suffix matching for *_api_key / *_password / etc.
//   - ScrubSettings: top-level redaction, deep dict recursion, deep list
//     recursion, mixed (list of dicts) recursion, presence preservation for
//     non-empty string secrets (replaced with ""), empty strings / ints /
//     nil left untouched, exact bare-name matching, camelCase keys, allow-
//     list bypass, webhook integration handle, non-dict input → {}.
//   - JSONScrubSettings: happy path, empty body, malformed JSON, top-level
//     non-object, JSON null.
//
// Behavioural parity with src/settings_scrub.py and tests/test_settings_scrub.py
// is the explicit goal of this file.
package settingsscrub

import (
	"bytes"
	"encoding/json"
	"reflect"
	"testing"
)

// ---- IsSecretKey ---------------------------------------------------------

func TestIsSecretKeyAllowListBypass(t *testing.T) {
	cases := []string{
		"google_pse_cx",
		"GOOGLE_PSE_CX",
		"google-pse-cx",
	}
	for _, c := range cases {
		if IsSecretKey(c) {
			t.Errorf("IsSecretKey(%q) = true, want false (allow-listed)", c)
		}
	}
}

func TestIsSecretKeySensitiveExact(t *testing.T) {
	cases := []string{
		"reminder_webhook_integration_id",
		"REMINDER_WEBHOOK_INTEGRATION_ID",
		"reminder-webhook-integration-id",
	}
	for _, c := range cases {
		if !IsSecretKey(c) {
			t.Errorf("IsSecretKey(%q) = false, want true (exact sensitive)", c)
		}
	}
}

func TestIsSecretKeySuffixPatterns(t *testing.T) {
	// Each entry pairs a real-world key with the trailing pattern from
	// _SECRET_KEY_PATTERNS that should cause it to be treated as a secret.
	cases := []struct {
		key  string
		want bool
	}{
		// trailing patterns
		{"openai_api_key", true},
		{"anthropic_api_key", true},
		{"smtp_password", true},
		{"smtp_pass", true},
		{"db_pwd", true},
		{"oauth_client_secret", true},
		{"gh_access_token", true},
		{"refresh_token", true},
		{"x_credential", true},
		{"x_credentials", true},
		{"z_apikey", true},
		{"search_api_key", true},
		// camelCase suffix
		{"apiKey", true},
		{"accessToken", true},
		{"refreshToken", true},
		{"clientSecret", true},
		{"hfToken", true},
		{"privateKey", true},
		// bare-name exact match (pattern stripped of leading underscore)
		{"password", true},
		{"token", true},
		{"secret", true},
		{"apikey", true},
		{"key", true},
		// non-secret keys must NOT trigger
		{"keybinds", false},
		{"theme", false},
		{"image_model", false},
		{"default_endpoint_id", false},
		{"search_result_count", false},
		{"tts_enabled", false},
		{"tokenId", false}, // becomes "token_id" which is NOT secret
		{"keyId", false},   // becomes "key_id" which is NOT secret
		{"google_pse_cx", false},
	}
	for _, tc := range cases {
		if got := IsSecretKey(tc.key); got != tc.want {
			t.Errorf("IsSecretKey(%q) = %v, want %v", tc.key, got, tc.want)
		}
	}
}

func TestCanonicalKeyName(t *testing.T) {
	cases := []struct {
		in, want string
	}{
		{"", ""},
		{"apiKey", "api_key"},
		{"accessToken", "access_token"},
		{"refreshToken", "refresh_token"},
		{"clientSecret", "client_secret"},
		{"privateKey", "private_key"},
		{"api_key", "api_key"},
		{"reminder_webhook_integration_id", "reminder_webhook_integration_id"},
		{"reminder-webhook-integration-id", "reminder_webhook_integration_id"},
		{"google-pse-cx", "google_pse_cx"},
		{"tokenId", "token_id"},
		{"keyId", "key_id"},
		{"hfToken", "hf_token"},
	}
	for _, tc := range cases {
		if got := canonicalKeyName(tc.in); got != tc.want {
			t.Errorf("canonicalKeyName(%q) = %q, want %q", tc.in, got, tc.want)
		}
	}
}

// ---- ScrubSettings -------------------------------------------------------

func TestScrubSettingsTopLevelSecretsBlank(t *testing.T) {
	in := map[string]any{
		"search_api_key": "S",
		"openai_api_key": "K",
		"smtp_password":  "P",
	}
	out := ScrubSettings(in)
	if out["search_api_key"] != "" || out["openai_api_key"] != "" || out["smtp_password"] != "" {
		t.Fatalf("expected secrets blanked, got %#v", out)
	}
}

func TestScrubSettingsBroadenedPatternsBlank(t *testing.T) {
	in := map[string]any{
		"smtp_pass":           "a",
		"db_pwd":              "b",
		"oauth_client_secret": "c",
		"gh_access_token":     "d",
		"refresh_token":       "e",
		"x_credential":        "f",
		"z_apikey":            "g",
	}
	out := ScrubSettings(in)
	for k, v := range in {
		if out[k] != "" {
			t.Errorf("out[%q] = %v, want \"\"", k, v)
		}
	}
}

func TestScrubSettingsNestedSecret(t *testing.T) {
	in := map[string]any{
		"email_account": map[string]any{
			"host":          "imap",
			"smtp_password": "NESTED",
		},
	}
	out := ScrubSettings(in)
	inner, ok := out["email_account"].(map[string]any)
	if !ok {
		t.Fatalf("email_account not a map: %#v", out["email_account"])
	}
	if inner["host"] != "imap" {
		t.Errorf("nested non-secret lost: %v", inner["host"])
	}
	if inner["smtp_password"] != "" {
		t.Errorf("nested secret not blanked: %v", inner["smtp_password"])
	}
}

func TestScrubSettingsSecretInListOfDicts(t *testing.T) {
	in := map[string]any{
		"providers": []any{
			map[string]any{"name": "a", "api_key": "P1"},
			map[string]any{"name": "b", "access_token": "T2"},
		},
	}
	out := ScrubSettings(in)
	list, ok := out["providers"].([]any)
	if !ok || len(list) != 2 {
		t.Fatalf("providers not a 2-element list: %#v", out["providers"])
	}
	first := list[0].(map[string]any)
	second := list[1].(map[string]any)
	if first["name"] != "a" {
		t.Errorf("first.name = %v", first["name"])
	}
	if first["api_key"] != "" {
		t.Errorf("first.api_key = %v", first["api_key"])
	}
	if second["access_token"] != "" {
		t.Errorf("second.access_token = %v", second["access_token"])
	}
}

func TestScrubSettingsNonSecretKeysPreserved(t *testing.T) {
	in := map[string]any{
		"keybinds":            map[string]any{"send": "Enter"},
		"theme":               "dark",
		"image_model":         "x",
		"default_endpoint_id": "ep1",
		"search_result_count": 5,
		"tts_enabled":         true,
		"tokenId":             "public-id",
		"keyId":               "public-key-id",
	}
	out := ScrubSettings(in)
	if !reflect.DeepEqual(out, in) {
		t.Errorf("non-secret map was modified:\nwant=%#v\ngot =%#v", in, out)
	}
}

func TestScrubSettingsGooglePSECXIsPublic(t *testing.T) {
	in := map[string]any{"google_pse_cx": "cx123"}
	out := ScrubSettings(in)
	if out["google_pse_cx"] != "cx123" {
		t.Errorf("google_pse_cx should be preserved, got %v", out["google_pse_cx"])
	}
}

func TestScrubSettingsWebhookIntegrationHandleBlank(t *testing.T) {
	in := map[string]any{
		"reminder_webhook_integration_id":   "global-webhook",
		"reminder_webhook_payload_template": `{"content":"{{message}}"}`,
	}
	if !IsSecretKey("reminder_webhook_integration_id") {
		t.Fatal("reminder_webhook_integration_id should be treated as secret")
	}
	out := ScrubSettings(in)
	if out["reminder_webhook_integration_id"] != "" {
		t.Errorf("integration id should be blanked, got %v", out["reminder_webhook_integration_id"])
	}
	if out["reminder_webhook_payload_template"] != `{"content":"{{message}}"}` {
		t.Errorf("payload template should be preserved, got %v", out["reminder_webhook_payload_template"])
	}
}

func TestScrubSettingsEmptyAndNonStringSecretValuesUntouched(t *testing.T) {
	in := map[string]any{
		"api_key":     "",
		"feature_key": 7,
		"x_token":     nil,
	}
	out := ScrubSettings(in)
	if out["api_key"] != "" {
		t.Errorf("empty api_key should stay empty, got %v", out["api_key"])
	}
	if out["feature_key"] != 7 {
		t.Errorf("non-string feature_key should not be blanked, got %v", out["feature_key"])
	}
	if out["x_token"] != nil {
		t.Errorf("nil x_token should stay nil, got %v", out["x_token"])
	}
}

func TestScrubSettingsExactNameMatches(t *testing.T) {
	in := map[string]any{
		"password": "p",
		"token":    "t",
		"secret":   "s",
		"apikey":   "a",
		"key":      "k",
	}
	out := ScrubSettings(in)
	for k, v := range out {
		if v != "" {
			t.Errorf("exact match %q not blanked: %v", k, v)
		}
	}
}

func TestScrubSettingsCamelCaseSecretKeysBlank(t *testing.T) {
	in := map[string]any{
		"apiKey":       "api-secret",
		"accessToken":  "access-secret",
		"refreshToken": "refresh-secret",
		"clientSecret": "client-secret",
		"hfToken":      "hf-secret",
		"nested": map[string]any{
			"privateKey": "private-secret",
		},
	}
	out := ScrubSettings(in)
	if out["apiKey"] != "" {
		t.Errorf("apiKey = %v", out["apiKey"])
	}
	if out["accessToken"] != "" {
		t.Errorf("accessToken = %v", out["accessToken"])
	}
	if out["refreshToken"] != "" {
		t.Errorf("refreshToken = %v", out["refreshToken"])
	}
	if out["clientSecret"] != "" {
		t.Errorf("clientSecret = %v", out["clientSecret"])
	}
	if out["hfToken"] != "" {
		t.Errorf("hfToken = %v", out["hfToken"])
	}
	nested := out["nested"].(map[string]any)
	if nested["privateKey"] != "" {
		t.Errorf("nested.privateKey = %v", nested["privateKey"])
	}
}

func TestScrubSettingsNonDictInputReturnsEmpty(t *testing.T) {
	out := ScrubSettings(nil)
	if out == nil {
		t.Fatal("ScrubSettings(nil) returned nil; want empty non-nil map")
	}
	if len(out) != 0 {
		t.Errorf("ScrubSettings(nil) = %v, want empty", out)
	}
}

func TestScrubSettingsDeeplyNestedListAndDict(t *testing.T) {
	// Mirrors a real-world providers[*].credentials.password layout.
	in := map[string]any{
		"providers": []any{
			map[string]any{
				"name": "p1",
				"credentials": map[string]any{
					"password": "p1-pass",
				},
			},
			map[string]any{
				"name": "p2",
				"credentials": []any{
					map[string]any{"token": "p2-tok-1"},
					map[string]any{"token": "p2-tok-2"},
				},
			},
		},
	}
	out := ScrubSettings(in)
	list := out["providers"].([]any)

	p1 := list[0].(map[string]any)["credentials"].(map[string]any)
	if p1["password"] != "" {
		t.Errorf("p1.credentials.password = %v", p1["password"])
	}

	p2creds := list[1].(map[string]any)["credentials"].([]any)
	if p2creds[0].(map[string]any)["token"] != "" {
		t.Errorf("p2.credentials[0].token not blanked")
	}
	if p2creds[1].(map[string]any)["token"] != "" {
		t.Errorf("p2.credentials[1].token not blanked")
	}
}

func TestScrubSettingsDoesNotMutateInput(t *testing.T) {
	in := map[string]any{
		"openai_api_key": "KEEP",
		"nested": map[string]any{
			"smtp_password": "KEEP",
		},
	}
	snapshot := map[string]any{
		"openai_api_key": "KEEP",
		"nested": map[string]any{
			"smtp_password": "KEEP",
		},
	}
	_ = ScrubSettings(in)
	if !reflect.DeepEqual(in, snapshot) {
		t.Errorf("input was mutated:\nwant=%#v\ngot =%#v", snapshot, in)
	}
}

// ---- JSONScrubSettings ---------------------------------------------------

func TestJSONScrubSettingsHappy(t *testing.T) {
	body := []byte(`{"openai_api_key":"K","theme":"dark"}`)
	out := JSONScrubSettings(body)
	if out["openai_api_key"] != "" {
		t.Errorf("openai_api_key not blanked: %v", out["openai_api_key"])
	}
	if out["theme"] != "dark" {
		t.Errorf("theme not preserved: %v", out["theme"])
	}
}

func TestJSONScrubSettingsEmptyBody(t *testing.T) {
	out := JSONScrubSettings(nil)
	if out == nil || len(out) != 0 {
		t.Errorf("nil body should yield empty non-nil map, got %#v", out)
	}
	out = JSONScrubSettings([]byte{})
	if out == nil || len(out) != 0 {
		t.Errorf("empty body should yield empty non-nil map, got %#v", out)
	}
}

func TestJSONScrubSettingsMalformed(t *testing.T) {
	out := JSONScrubSettings([]byte(`{"openai_api_key": "K"`)) // truncated
	if out == nil || len(out) != 0 {
		t.Errorf("malformed JSON should yield empty map, got %#v", out)
	}
}

func TestJSONScrubSettingsTopLevelNonObject(t *testing.T) {
	out := JSONScrubSettings([]byte(`["not", "settings"]`))
	if out == nil || len(out) != 0 {
		t.Errorf("non-object JSON should yield empty map, got %#v", out)
	}
	out = JSONScrubSettings([]byte(`"not settings"`))
	if out == nil || len(out) != 0 {
		t.Errorf("top-level string JSON should yield empty map, got %#v", out)
	}
}

func TestJSONScrubSettingsNullTopLevel(t *testing.T) {
	out := JSONScrubSettings([]byte(`null`))
	if out == nil || len(out) != 0 {
		t.Errorf("JSON null should yield empty map, got %#v", out)
	}
}

func TestJSONScrubSettingsNestedSecret(t *testing.T) {
	body := []byte(`{"email_account":{"host":"imap","smtp_password":"NESTED"}}`)
	out := JSONScrubSettings(body)
	inner, ok := out["email_account"].(map[string]any)
	if !ok {
		t.Fatalf("email_account not a map: %#v", out["email_account"])
	}
	if inner["host"] != "imap" {
		t.Errorf("nested non-secret lost: %v", inner["host"])
	}
	if inner["smtp_password"] != "" {
		t.Errorf("nested secret not blanked: %v", inner["smtp_password"])
	}
}

func TestJSONScrubSettingsRoundTrip(t *testing.T) {
	// Sanity: scrub, then re-marshal via stdlib, ensure the redacted shape
	// matches a hand-rolled expected map. This catches regressions where
	// scrubValue accidentally drops or re-encodes keys.
	in := map[string]any{
		"openai_api_key":                  "K",
		"theme":                           "dark",
		"keybinds":                        map[string]any{"send": "Enter"},
		"reminder_webhook_integration_id": "global",
	}
	body, err := json.Marshal(in)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	out := JSONScrubSettings(body)
	var buf bytes.Buffer
	if err := json.NewEncoder(&buf).Encode(out); err != nil {
		t.Fatalf("re-encode: %v", err)
	}
	var decoded map[string]any
	if err := json.Unmarshal(buf.Bytes(), &decoded); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if decoded["openai_api_key"] != "" {
		t.Errorf("openai_api_key round-trip not blanked")
	}
	if decoded["theme"] != "dark" {
		t.Errorf("theme round-trip lost: %v", decoded["theme"])
	}
	if decoded["reminder_webhook_integration_id"] != "" {
		t.Errorf("integration id round-trip not blanked")
	}
}
