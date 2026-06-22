package aiinteraction

import (
	"context"
	"fmt"
	"strings"
	"testing"
)

func TestParseModelSpec(t *testing.T) {
	tests := []struct {
		name    string
		spec    string
		wantMod string
		wantEnd string
		wantErr bool
	}{
		{"plain", "gpt-4", "gpt-4", "", false},
		{"at", "gpt-4@my-endpoint", "gpt-4", "my-endpoint", false},
		{"trim", "  gpt-4 @ my-endpoint  ", "gpt-4", "my-endpoint", false},
		{"empty", "", "", "", true},
		{"no_model", "@endpoint", "", "", true},
		{"no_endpoint", "model@", "", "", true},
		{"multi_at", "gpt-4@host@path", "gpt-4@host", "path", false},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got, err := ParseModelSpec(tc.spec)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("want error, got %+v", got)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got.ModelName != tc.wantMod {
				t.Errorf("model = %q, want %q", got.ModelName, tc.wantMod)
			}
			if got.EndpointName != tc.wantEnd {
				t.Errorf("endpoint = %q, want %q", got.EndpointName, tc.wantEnd)
			}
		})
	}
}

func TestBuildChatURL(t *testing.T) {
	tests := []struct {
		base string
		want string
	}{
		{"https://api.openai.com/v1", "https://api.openai.com/v1/chat/completions"},
		{"https://api.openai.com", "https://api.openai.com/v1/chat/completions"},
		{"http://localhost:11434/api", "http://localhost:11434/api/chat"},
		{"https://api.deepseek.com", "https://api.deepseek.com/chat/completions"},
		{"https://api.anthropic.com", "https://api.anthropic.com/v1/messages"},
		{"https://api.openai.com/", "https://api.openai.com/v1/chat/completions"},
	}
	for _, tc := range tests {
		t.Run(tc.base, func(t *testing.T) {
			got := BuildChatURL(tc.base)
			if got != tc.want {
				t.Errorf("BuildChatURL(%q) = %q, want %q", tc.base, got, tc.want)
			}
		})
	}
}

func TestBuildModelsURL(t *testing.T) {
	tests := []struct {
		base string
		want string
	}{
		{"https://api.openai.com/v1", "https://api.openai.com/v1/models"},
		{"https://api.openai.com", "https://api.openai.com/v1/models"},
		{"http://localhost:11434/api", "http://localhost:11434/api/tags"},
		{"https://api.anthropic.com", "https://api.anthropic.com/v1/models"},
		{"http://localhost:8000", "http://localhost:8000/v1/models"},
	}
	for _, tc := range tests {
		t.Run(tc.base, func(t *testing.T) {
			got := BuildModelsURL(tc.base)
			if got != tc.want {
				t.Errorf("BuildModelsURL(%q) = %q, want %q", tc.base, got, tc.want)
			}
		})
	}
}

func TestBuildHeaders(t *testing.T) {
	tests := []struct {
		name    string
		apiKey  string
		base    string
		wantKV  map[string]string
		wantHas []string
	}{
		{
			name:   "openai",
			apiKey: "sk-abc",
			base:   "https://api.openai.com",
			wantKV: map[string]string{"Authorization": "Bearer sk-abc"},
		},
		{
			name:   "anthropic",
			apiKey: "sk-ant",
			base:   "https://api.anthropic.com",
			wantKV: map[string]string{
				"x-api-key":         "sk-ant",
				"anthropic-version": "2023-06-01",
			},
		},
		{
			name:   "openrouter",
			apiKey: "or-key",
			base:   "https://openrouter.ai/api/v1",
			wantKV: map[string]string{
				"Authorization":      "Bearer or-key",
				"HTTP-Referer":       "https://github.com/pewdiepie-archdaemon/odysseus",
				"X-OpenRouter-Title": "Odysseus",
			},
		},
	}
	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := BuildHeaders(tc.apiKey, tc.base)
			for k, v := range tc.wantKV {
				if got[k] != v {
					t.Errorf("header[%q] = %q, want %q", k, got[k], v)
				}
			}
			if len(got) != len(tc.wantKV) {
				t.Errorf("got %d headers, want %d (got=%v)", len(got), len(tc.wantKV), got)
			}
		})
	}
}

func TestDetectProvider(t *testing.T) {
	tests := []struct {
		base string
		want string
	}{
		{"https://api.openai.com", "openai"},
		{"https://api.openai.com/v1", "openai"},
		{"https://api.anthropic.com", "anthropic"},
		{"https://api.anthropic.com/v1", "anthropic"},
		{"https://openrouter.ai/api/v1", "openrouter"},
		{"http://localhost:11434/api", "ollama"},
		{"http://localhost:8000", "openai"},
		{"https://api.deepseek.com", "openai"},
		{"https://api.groq.com/openai/v1", "groq"},
	}
	for _, tc := range tests {
		t.Run(tc.base, func(t *testing.T) {
			got := detectProvider(tc.base)
			if got != tc.want {
				t.Errorf("detectProvider(%q) = %q, want %q", tc.base, got, tc.want)
			}
		})
	}
}

func TestHostMatch(t *testing.T) {
	tests := []struct {
		host, suffix string
		want         bool
	}{
		{"api.openai.com", "openai.com", true},
		{"api.foo.openai.com", "openai.com", true},
		{"openai.com.evil.com", "openai.com", false},
		{"openai.com", "openai.com", true},
		{"example.com", "openai.com", false},
	}
	for _, tc := range tests {
		t.Run(tc.host+"_"+tc.suffix, func(t *testing.T) {
			got := hostMatch(tc.host, tc.suffix)
			if got != tc.want {
				t.Errorf("hostMatch(%q, %q) = %v, want %v", tc.host, tc.suffix, got, tc.want)
			}
		})
	}
}

func TestIsOllamaNative(t *testing.T) {
	tests := []struct {
		rawURL string
		want   bool
	}{
		{"http://localhost:11434/api", true},
		{"http://localhost:11434", true},
		{"http://localhost:11434/api/chat", true},
		{"http://localhost:11434/v1/chat/completions", false},
		{"http://127.0.0.1:11434/api", true},
		{"http://0.0.0.0:11434", true},
		// Localhost on a non-default port with /api path: ambiguous.
		// The Python source returns True (host is local + path is
		// /api). The Go port matches.
		{"http://localhost:9000/api", true},
		{"https://api.ollama.com", true},
		{"https://example.com", false},
	}
	for _, tc := range tests {
		t.Run(tc.rawURL, func(t *testing.T) {
			got := isOllamaNative(tc.rawURL)
			if got != tc.want {
				t.Errorf("isOllamaNative(%q) = %v, want %v", tc.rawURL, got, tc.want)
			}
		})
	}
}

func TestAppendPath(t *testing.T) {
	tests := []struct{ base, path, want string }{
		{"", "/x", "/x"},
		{"a", "/b", "a/b"},
		{"a/", "/b", "a/b"},
		{"a", "b", "a/b"},
		{"a/", "b", "a/b"},
	}
	for _, tc := range tests {
		t.Run(tc.base+"_"+tc.path, func(t *testing.T) {
			got := appendPath(tc.base, tc.path)
			if got != tc.want {
				t.Errorf("appendPath(%q, %q) = %q, want %q", tc.base, tc.path, got, tc.want)
			}
		})
	}
}

func TestResolveModel_NoStore(t *testing.T) {
	_, err := ResolveModel("gpt-4", ResolveOptions{})
	if err == nil {
		t.Fatalf("expected error when store is nil")
	}
}

func TestResolveModel_NotFound(t *testing.T) {
	store := fakeStore{eps: []EndpointRecord{
		{Name: "ep1", BaseURL: "https://api.openai.com", CachedModels: []string{"gpt-3.5-turbo"}},
	}}
	rt := func(r EndpointRecord, owner string) (string, string, error) {
		return r.BaseURL, "key", nil
	}
	_, err := ResolveModel("gpt-99", ResolveOptions{Store: store, Runtime: rt})
	if err == nil {
		t.Fatalf("expected error for missing model")
	}
	if !strings.Contains(err.Error(), "gpt-99") {
		t.Errorf("error should mention model name, got %v", err)
	}
}

func TestResolveModel_ExactMatch(t *testing.T) {
	store := fakeStore{eps: []EndpointRecord{
		{Name: "ep1", BaseURL: "https://api.openai.com", CachedModels: []string{"gpt-4", "gpt-3.5-turbo"}},
	}}
	rt := func(r EndpointRecord, owner string) (string, string, error) {
		return r.BaseURL, "key", nil
	}
	res, err := ResolveModel("gpt-4", ResolveOptions{Store: store, Runtime: rt})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if res.ModelID != "gpt-4" {
		t.Errorf("ModelID = %q, want gpt-4", res.ModelID)
	}
	if !strings.Contains(res.EndpointURL, "chat/completions") {
		t.Errorf("EndpointURL = %q, want chat/completions", res.EndpointURL)
	}
}

func TestResolveModel_PartialMatch(t *testing.T) {
	store := fakeStore{eps: []EndpointRecord{
		{Name: "ep1", BaseURL: "https://api.openai.com", CachedModels: []string{"gpt-4-turbo-preview"}},
	}}
	rt := func(r EndpointRecord, owner string) (string, string, error) {
		return r.BaseURL, "key", nil
	}
	res, err := ResolveModel("gpt-4", ResolveOptions{Store: store, Runtime: rt})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !strings.Contains(res.ModelID, "gpt-4") {
		t.Errorf("ModelID = %q, want contains gpt-4", res.ModelID)
	}
}

func TestResolveModel_AnthropicMatch(t *testing.T) {
	store := fakeStore{eps: []EndpointRecord{
		{Name: "ep1", BaseURL: "https://api.anthropic.com", CachedModels: nil},
	}}
	rt := func(r EndpointRecord, owner string) (string, string, error) {
		return r.BaseURL, "sk-ant", nil
	}
	res, err := ResolveModel("sonnet", ResolveOptions{Store: store, Runtime: rt})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if !strings.Contains(res.ModelID, "sonnet") {
		t.Errorf("ModelID = %q, want contains sonnet", res.ModelID)
	}
	if !strings.Contains(res.EndpointURL, "messages") {
		t.Errorf("EndpointURL = %q, want messages", res.EndpointURL)
	}
	if res.Headers["x-api-key"] != "sk-ant" {
		t.Errorf("anthropic x-api-key header missing")
	}
}

func TestResolveModel_FiltersByName(t *testing.T) {
	store := fakeStore{eps: []EndpointRecord{
		{Name: "ep1", BaseURL: "https://api.openai.com", CachedModels: []string{"gpt-4"}},
		{Name: "ep-other", BaseURL: "https://api.deepseek.com", CachedModels: []string{"deepseek-chat"}},
	}}
	rt := func(r EndpointRecord, owner string) (string, string, error) {
		return r.BaseURL, "key", nil
	}
	// spec "gpt-4@ep-other" should NOT match — ep-other does not carry
	// "gpt-4" in its cached models, even though ep1 does. The fakeStore
	// filter narrows to ep-other only, so the resolver cannot fall
	// through to ep1.
	_, err := ResolveModel("gpt-4@ep-other", ResolveOptions{Store: store, Runtime: rt})
	if err == nil {
		t.Fatalf("expected error when model not present on filtered endpoint")
	}
	if !strings.Contains(err.Error(), "not found") {
		t.Errorf("expected 'not found' error, got %v", err)
	}
}

func TestResolveModel_FiltersByName_Hits(t *testing.T) {
	store := fakeStore{eps: []EndpointRecord{
		{Name: "ep1", BaseURL: "https://api.openai.com", CachedModels: []string{"gpt-4"}},
		{Name: "ep-other", BaseURL: "https://api.deepseek.com", CachedModels: []string{"deepseek-chat"}},
	}}
	rt := func(r EndpointRecord, owner string) (string, string, error) {
		return r.BaseURL, "key", nil
	}
	res, err := ResolveModel("gpt-4@ep1", ResolveOptions{Store: store, Runtime: rt})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if res.ModelID != "gpt-4" {
		t.Errorf("ModelID = %q, want gpt-4", res.ModelID)
	}
}

// fakeStore is a minimal ModelEndpointStore for tests.
type fakeStore struct {
	eps []EndpointRecord
}

func (f fakeStore) EnabledEndpoints(nameContains, owner string) []EndpointRecord {
	out := make([]EndpointRecord, 0, len(f.eps))
	for _, e := range f.eps {
		if nameContains != "" && !strings.Contains(strings.ToLower(e.Name), strings.ToLower(nameContains)) {
			continue
		}
		out = append(out, e)
	}
	return out
}

// LLMCall is referenced from the dispatch layer; expose a smoke test
// that round-trips the LLMCall type to ensure it remains a func.
var _ LLMCall = func(ctx context.Context, url, model string, headers map[string]string, msgs []ChatMessage, to int) (string, error) {
	return "ok", nil
}

var _ = fmt.Sprintf
