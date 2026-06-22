package taskendpoint

import (
	"reflect"
	"testing"
)

func TestResolve_AdminOverridesFallback(t *testing.T) {
	settings := Settings{
		EndpointID:      "task-primary",
		EndpointURL:     "https://admin.example/v1",
		EndpointModel:   "admin-model",
		EndpointHeaders: map[string]string{"X-Admin": "yes"},
	}
	got := Resolve(settings, "https://fallback.example/v1", "fallback-model",
		map[string]string{"X-Fallback": "yes"}, "owner-1")

	want := Resolution{
		URL:   "https://admin.example/v1",
		Model: "admin-model",
		Headers: map[string]string{
			"X-Admin":    "yes",
			"X-Fallback": "yes",
		},
		Source: "admin",
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("Resolve(admin) = %+v, want %+v", got, want)
	}
}

func TestResolve_AdminURLWithoutModelUsesFallbackModel(t *testing.T) {
	settings := Settings{
		EndpointID:  "task-primary",
		EndpointURL: "https://admin.example/v1",
	}
	got := Resolve(settings, "https://fallback.example/v1", "fallback-model", nil, "")
	if got.Model != "fallback-model" {
		t.Errorf("Model = %q, want fallback-model", got.Model)
	}
	if got.Source != "admin" {
		t.Errorf("Source = %q, want admin", got.Source)
	}
	if got.URL != "https://admin.example/v1" {
		t.Errorf("URL = %q, want admin URL", got.URL)
	}
}

func TestResolve_NoAdminUsesFallback(t *testing.T) {
	settings := Settings{}
	got := Resolve(settings, "https://fallback.example/v1", "fallback-model",
		map[string]string{"Authorization": "Bearer xyz"}, "")

	want := Resolution{
		URL:     "https://fallback.example/v1",
		Model:   "fallback-model",
		Headers: map[string]string{"Authorization": "Bearer xyz"},
		Source:  "fallback",
	}
	if !reflect.DeepEqual(got, want) {
		t.Errorf("Resolve(fallback) = %+v, want %+v", got, want)
	}
}

func TestResolve_NothingConfiguredReturnsEmpty(t *testing.T) {
	got := Resolve(Settings{}, "", "", nil, "")
	if got.Source != "empty" {
		t.Errorf("Source = %q, want empty", got.Source)
	}
	if got.URL != "" || got.Model != "" {
		t.Errorf("expected empty URL/Model, got %+v", got)
	}
	if got.Headers != nil {
		t.Errorf("expected nil Headers, got %+v", got.Headers)
	}
}

func TestResolve_WhitespaceAdminURLFallsBack(t *testing.T) {
	// The Python source checks "fall back when the setting is empty".
	// In Go we treat whitespace-only URLs as empty to mirror that.
	settings := Settings{EndpointURL: "   ", EndpointModel: "  "}
	got := Resolve(settings, "https://fallback.example/v1", "m", nil, "")
	if got.Source != "fallback" {
		t.Errorf("Source = %q, want fallback", got.Source)
	}
	if got.URL != "https://fallback.example/v1" {
		t.Errorf("URL = %q, want fallback URL", got.URL)
	}
}

func TestResolve_AdminHeadersWinOverFallback(t *testing.T) {
	// When the same key is present in both maps, the admin value wins.
	// This mirrors Python's dict.update semantics that the underlying
	// resolve_endpoint uses when merging per-endpoint headers.
	settings := Settings{
		EndpointURL:     "https://admin.example/v1",
		EndpointHeaders: map[string]string{"X-Same": "admin", "X-Admin": "a"},
	}
	got := Resolve(settings, "", "",
		map[string]string{"X-Same": "fallback", "X-Fallback": "b"}, "")
	if got.Headers["X-Same"] != "admin" {
		t.Errorf("X-Same = %q, want admin", got.Headers["X-Same"])
	}
	if got.Headers["X-Admin"] != "a" {
		t.Errorf("X-Admin = %q, want a", got.Headers["X-Admin"])
	}
	if got.Headers["X-Fallback"] != "b" {
		t.Errorf("X-Fallback = %q, want b", got.Headers["X-Fallback"])
	}
}

func TestResolve_ReturnedHeadersAreIndependent(t *testing.T) {
	// Mutating the result must not mutate the fallback map.
	fb := map[string]string{"X-Token": "abc"}
	got := Resolve(Settings{}, "u", "m", fb, "")
	got.Headers["X-Token"] = "mutated"
	if fb["X-Token"] != "abc" {
		t.Errorf("fallback map was mutated: %+v", fb)
	}
}

func TestMergeHeaders_NilSafe(t *testing.T) {
	out := mergeHeaders(nil, map[string]string{"a": "1"})
	if !reflect.DeepEqual(out, map[string]string{"a": "1"}) {
		t.Errorf("mergeHeaders(nil, {a:1}) = %+v, want {a:1}", out)
	}
	out2 := mergeHeaders(map[string]string{"a": "1"}, nil)
	if !reflect.DeepEqual(out2, map[string]string{"a": "1"}) {
		t.Errorf("mergeHeaders({a:1}, nil) = %+v, want {a:1}", out2)
	}
}

func TestCopyHeaders_NilSafe(t *testing.T) {
	if c := copyHeaders(nil); c != nil {
		t.Errorf("copyHeaders(nil) = %+v, want nil", c)
	}
	if c := copyHeaders(map[string]string{}); c != nil {
		t.Errorf("copyHeaders({}) = %+v, want nil", c)
	}
	c := copyHeaders(map[string]string{"a": "1"})
	if !reflect.DeepEqual(c, map[string]string{"a": "1"}) {
		t.Errorf("copyHeaders({a:1}) = %+v, want {a:1}", c)
	}
}
