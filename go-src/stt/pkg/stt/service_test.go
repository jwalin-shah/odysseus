package stt

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

// ── Helpers ──

func writeSettings(t *testing.T, dir string, s map[string]any) {
	t.Helper()
	data, err := json.Marshal(s)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(dir, "data"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "data", "settings.json"), data, 0644); err != nil {
		t.Fatal(err)
	}
}

func writeEndpoints(t *testing.T, dir string, eps map[string]ModelEndpoint) {
	t.Helper()
	data, err := json.Marshal(eps)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(dir, "data"), 0755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "data", "endpoints.json"), data, 0644); err != nil {
		t.Fatal(err)
	}
}

// ── Tests ──

func TestAvailable_Disabled(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  false,
		"stt_provider": "local",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	if s.Available() {
		t.Error("expected Available()=false when stt_enabled=false")
	}
}

func TestAvailable_Browser(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "browser",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	if !s.Available() {
		t.Error("expected Available()=true for browser provider")
	}
}

func TestAvailable_Endpoint(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "endpoint:test-ep",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	if !s.Available() {
		t.Error("expected Available()=true for endpoint provider")
	}
}

func TestTranscribe_Disabled(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  false,
		"stt_provider": "local",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	text, err := s.Transcribe(context.Background(), []byte("fake-audio"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if text != "" {
		t.Errorf("expected empty text, got %q", text)
	}
}

func TestTranscribe_Browser(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "browser",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	text, err := s.Transcribe(context.Background(), []byte("fake-audio"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if text != "" {
		t.Errorf("expected empty text for browser, got %q", text)
	}
}

func TestTranscribe_API(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "endpoint:test-ep",
		"stt_model":    "whisper-1",
	})
	writeEndpoints(t, dir, map[string]ModelEndpoint{
		"test-ep": {BaseURL: "", APIKey: "sk-test"},
	})

	// Start a test server that echoes back the transcription.
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			t.Errorf("expected POST, got %s", r.Method)
		}
		if r.Header.Get("Authorization") != "Bearer sk-test" {
			t.Errorf("expected Bearer token, got %q", r.Header.Get("Authorization"))
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"text":"hello world"}`))
	}))
	defer server.Close()

	// Update the endpoint with the test server URL.
	writeEndpoints(t, dir, map[string]ModelEndpoint{
		"test-ep": {BaseURL: server.URL, APIKey: "sk-test"},
	})

	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	text, err := s.Transcribe(context.Background(), []byte("fake-audio"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if text != "hello world" {
		t.Errorf("expected 'hello world', got %q", text)
	}
}

func TestTranscribe_API_NoAuth(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "endpoint:test-ep",
		"stt_model":    "whisper-1",
	})

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "" {
			t.Errorf("expected no auth header, got %q", r.Header.Get("Authorization"))
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"text":"no auth test"}`))
	}))
	defer server.Close()

	writeEndpoints(t, dir, map[string]ModelEndpoint{
		"test-ep": {BaseURL: server.URL, APIKey: ""},
	})

	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	text, err := s.Transcribe(context.Background(), []byte("fake-audio"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if text != "no auth test" {
		t.Errorf("expected 'no auth test', got %q", text)
	}
}

func TestTranscribe_API_Error(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "endpoint:test-ep",
		"stt_model":    "whisper-1",
	})

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		w.Write([]byte(`{"error":"bad request"}`))
	}))
	defer server.Close()

	writeEndpoints(t, dir, map[string]ModelEndpoint{
		"test-ep": {BaseURL: server.URL, APIKey: ""},
	})

	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	_, err := s.Transcribe(context.Background(), []byte("fake-audio"))
	if err == nil {
		t.Fatal("expected error for bad request, got nil")
	}
}

func TestTranscribe_API_EndpointNotFound(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "endpoint:nonexistent",
		"stt_model":    "whisper-1",
	})
	writeEndpoints(t, dir, map[string]ModelEndpoint{})

	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	_, err := s.Transcribe(context.Background(), []byte("fake-audio"))
	if err == nil {
		t.Fatal("expected error for missing endpoint, got nil")
	}
}

func TestTranscribe_UnknownProvider(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "unknown",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	_, err := s.Transcribe(context.Background(), []byte("fake-audio"))
	if err == nil {
		t.Fatal("expected error for unknown provider, got nil")
	}
}

func TestStats_Disabled(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  false,
		"stt_provider": "local",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	st := s.Stats()
	if st.Available {
		t.Error("expected Available=false when disabled")
	}
	if st.Provider != "disabled" {
		t.Errorf("expected provider=disabled, got %q", st.Provider)
	}
}

func TestStats_Browser(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "browser",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	st := s.Stats()
	if !st.Available {
		t.Error("expected Available=true for browser")
	}
	if st.Model != "Browser (Web Speech API)" {
		t.Errorf("expected model='Browser (Web Speech API)', got %q", st.Model)
	}
}

func TestStats_Endpoint(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "endpoint:my-ep",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	st := s.Stats()
	if !st.Available {
		t.Error("expected Available=true for endpoint")
	}
	if st.EndpointID != "my-ep" {
		t.Errorf("expected endpoint_id=my-ep, got %q", st.EndpointID)
	}
}

func TestGetSTTService_Singleton(t *testing.T) {
	s1 := GetSTTService()
	s2 := GetSTTService()
	if s1 != s2 {
		t.Error("GetSTTService() should return the same instance")
	}
}

func TestLoadSettings_Defaults(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s, err := loadSettings()
	if err != nil {
		t.Fatalf("loadSettings: %v", err)
	}
	if s.STTEnabled {
		t.Error("expected STTEnabled=false by default")
	}
	if s.STTProvider != "disabled" {
		t.Errorf("expected STTProvider=disabled, got %q", s.STTProvider)
	}
	if s.STTModel != "base" {
		t.Errorf("expected STTModel=base, got %q", s.STTModel)
	}
}

func TestLoadSettings_MissingFile(t *testing.T) {
	dir := t.TempDir()
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	_, err := loadSettings()
	if err == nil {
		t.Fatal("expected error for missing settings file")
	}
}

func TestLoadEndpoint_MissingFile(t *testing.T) {
	dir := t.TempDir()
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	_, err := loadEndpoint("test")
	if err == nil {
		t.Fatal("expected error for missing endpoints file")
	}
}

func TestLoadEndpoint_NotFound(t *testing.T) {
	dir := t.TempDir()
	writeEndpoints(t, dir, map[string]ModelEndpoint{})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	_, err := loadEndpoint("nonexistent")
	if err == nil {
		t.Fatal("expected error for missing endpoint")
	}
}

func TestAvailable_Local_NoWhisper(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "local",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	// Without a real whisper model, Available() should return false.
	if s.Available() {
		t.Error("expected Available()=false for local without whisper model")
	}
}

func TestTranscribe_Local_NoWhisper(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "local",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	_, err := s.Transcribe(context.Background(), []byte("fake-audio"))
	if err == nil {
		t.Fatal("expected error for local without whisper model")
	}
}

func TestAvailable_DisabledProvider(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "disabled",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	if s.Available() {
		t.Error("expected Available()=false for disabled provider")
	}
}

func TestTranscribe_API_WithLanguage(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "endpoint:test-ep",
		"stt_model":    "whisper-1",
		"stt_language": "en",
	})

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if err := r.ParseMultipartForm(1 << 20); err != nil {
			t.Fatal(err)
		}
		if lang := r.FormValue("language"); lang != "en" {
			t.Errorf("expected language=en, got %q", lang)
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"text":"hello with language"}`))
	}))
	defer server.Close()

	writeEndpoints(t, dir, map[string]ModelEndpoint{
		"test-ep": {BaseURL: server.URL, APIKey: ""},
	})

	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	text, err := s.Transcribe(context.Background(), []byte("fake-audio"))
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if text != "hello with language" {
		t.Errorf("expected 'hello with language', got %q", text)
	}
}

func TestStats_Local(t *testing.T) {
	dir := t.TempDir()
	writeSettings(t, dir, map[string]any{
		"stt_enabled":  true,
		"stt_provider": "local",
		"stt_model":    "base",
	})
	origWd, _ := os.Getwd()
	os.Chdir(dir)
	defer os.Chdir(origWd)

	s := New()
	st := s.Stats()
	if st.Provider != "local" {
		t.Errorf("expected provider=local, got %q", st.Provider)
	}
	if st.Model != "base" {
		t.Errorf("expected model=base, got %q", st.Model)
	}
	// Model should not be loaded since we have no real whisper.
	if st.ModelLoaded {
		t.Error("expected ModelLoaded=false without whisper model")
	}
}
