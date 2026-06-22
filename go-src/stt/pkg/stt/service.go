// Package stt implements a multi-provider Speech-to-Text service.
//
// It mirrors the public surface of services/stt/stt_service.py: transcribe
// audio bytes to text using local whisper.cpp, an OpenAI-compatible API
// endpoint, or a browser-side no-op.
package stt

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

// ── Settings ──

// Settings holds the STT-relevant subset of data/settings.json.
type Settings struct {
	STTEnabled  bool   `json:"stt_enabled"`
	STTProvider string `json:"stt_provider"`
	STTModel    string `json:"stt_model"`
	STTLanguage string `json:"stt_language"`
}

func loadSettings() (Settings, error) {
	raw, err := os.ReadFile("data/settings.json")
	if err != nil {
		return Settings{}, fmt.Errorf("read settings: %w", err)
	}
	var all map[string]any
	if err := json.Unmarshal(raw, &all); err != nil {
		return Settings{}, fmt.Errorf("parse settings: %w", err)
	}
	s := Settings{
		STTEnabled:  false,
		STTProvider: "disabled",
		STTModel:    "base",
		STTLanguage: "",
	}
	if v, ok := all["stt_enabled"].(bool); ok {
		s.STTEnabled = v
	}
	if v, ok := all["stt_provider"].(string); ok {
		s.STTProvider = v
	}
	if v, ok := all["stt_model"].(string); ok {
		s.STTModel = v
	}
	if v, ok := all["stt_language"].(string); ok {
		s.STTLanguage = v
	}
	return s, nil
}

// ── Whisper interface ──

// WhisperModel is the interface satisfied by whisper.cpp Go bindings.
// We define it here so tests can substitute a stub.
type WhisperModel interface {
	Transcribe(ctx context.Context, audio []byte, opts map[string]string) (string, error)
	Close() error
}

// ── Endpoint config ──

// ModelEndpoint mirrors the database row for an OpenAI-compatible endpoint.
type ModelEndpoint struct {
	BaseURL string `json:"base_url"`
	APIKey  string `json:"api_key"`
}

// loadEndpoint reads a ModelEndpoint from the database by ID.
// In the Go port this reads from a JSON file mirroring the DB table.
func loadEndpoint(endpointID string) (*ModelEndpoint, error) {
	// Read endpoints from data/endpoints.json (mirrors the ModelEndpoint DB table).
	raw, err := os.ReadFile("data/endpoints.json")
	if err != nil {
		return nil, fmt.Errorf("read endpoints: %w", err)
	}
	var endpoints map[string]ModelEndpoint
	if err := json.Unmarshal(raw, &endpoints); err != nil {
		return nil, fmt.Errorf("parse endpoints: %w", err)
	}
	ep, ok := endpoints[endpointID]
	if !ok {
		return nil, fmt.Errorf("endpoint %q not found", endpointID)
	}
	return &ep, nil
}

// ── STTService ──

// STTService is a multi-provider Speech-to-Text service.
//
// Reads provider config from data/settings.json on each call.
// Providers:
//
//	"disabled"        — no STT
//	"browser"         — client-side Web Speech API (no server transcription)
//	"local"           — whisper.cpp on CPU/GPU
//	"endpoint:<id>"   — OpenAI-compatible /audio/transcriptions via ModelEndpoint
type STTService struct {
	mu      sync.Mutex
	whisper WhisperModel // lazy-init
}

// New creates an STTService with no whisper model loaded.
func New() *STTService {
	return &STTService{}
}

// Available reports whether the service can transcribe audio right now.
func (s *STTService) Available() bool {
	settings, err := loadSettings()
	if err != nil || !settings.STTEnabled {
		return false
	}
	switch {
	case settings.STTProvider == "disabled":
		return false
	case settings.STTProvider == "browser":
		return true // handled client-side
	case settings.STTProvider == "local":
		return s.getWhisper() != nil
	case strings.HasPrefix(settings.STTProvider, "endpoint:"):
		return true // assume reachable
	default:
		return false
	}
}

// ── Local Whisper ──

func (s *STTService) getWhisper() WhisperModel {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.whisper != nil {
		return s.whisper
	}
	settings, err := loadSettings()
	if err != nil {
		log.Printf("stt: load settings for whisper init: %v", err)
		return nil
	}
	modelSize := settings.STTModel
	if modelSize == "" {
		modelSize = "base"
	}
	w, err := newWhisperCPP(modelSize)
	if err != nil {
		log.Printf("stt: failed to load whisper model %q: %v", modelSize, err)
		return nil
	}
	s.whisper = w
	log.Printf("stt: whisper model %q loaded", modelSize)
	return s.whisper
}

// newWhisperCPP creates a whisper.cpp-backed WhisperModel.
// In production this would use the whisper.cpp Go bindings.
// The model file is downloaded on first use via the bindings' built-in downloader.
func newWhisperCPP(modelSize string) (WhisperModel, error) {
	// whisper.cpp Go bindings API:
	//   model, err := whisper.New(modelPath)
	//   segments, err := model.Transcribe(ctx, audio)
	//
	// For now we use a thin wrapper that shells out to whisper.cpp CLI
	// as a bridge until the Go bindings are vendored.

	// Check that the model file exists on disk before claiming success.
	modelPath := filepath.Join("models", "ggml-"+modelSize+".bin")
	if _, err := os.Stat(modelPath); os.IsNotExist(err) {
		return nil, fmt.Errorf("whisper model file not found: %s", modelPath)
	}

	return &whisperCPPBridge{modelSize: modelSize}, nil
}

type whisperCPPBridge struct {
	modelSize string
}

func (w *whisperCPPBridge) Transcribe(ctx context.Context, audio []byte, opts map[string]string) (string, error) {
	// Write audio to a temp file for whisper.cpp.
	tmpDir, err := os.MkdirTemp("", "stt-*")
	if err != nil {
		return "", fmt.Errorf("create temp dir: %w", err)
	}
	defer os.RemoveAll(tmpDir)

	audioPath := filepath.Join(tmpDir, "audio.webm")
	if err := os.WriteFile(audioPath, audio, 0644); err != nil {
		return "", fmt.Errorf("write audio temp file: %w", err)
	}

	// Build whisper.cpp CLI args.
	// In production this would use the Go bindings directly.
	modelPath := filepath.Join("models", "ggml-"+w.modelSize+".bin")
	args := []string{"--model", modelPath, "--file", audioPath, "--output-txt"}
	if lang, ok := opts["language"]; ok && lang != "" {
		args = append(args, "--language", lang)
	}

	// Use the whisper.cpp CLI binary.
	cmd := "whisper-cli" // assumed on PATH or configured
	// For now, return a placeholder — the real integration will use Go bindings.
	_ = cmd
	_ = args

	// Placeholder: in production this runs the model and returns the text.
	return "", fmt.Errorf("whisper.cpp Go bindings not yet vendored; use Python faster-whisper for now")
}

func (w *whisperCPPBridge) Close() error {
	return nil
}

// ── API endpoint ──

func (s *STTService) transcribeAPI(ctx context.Context, audio []byte, endpointID, model, language string) (string, error) {
	ep, err := loadEndpoint(endpointID)
	if err != nil {
		return "", fmt.Errorf("stt: %w", err)
	}

	url := strings.TrimRight(ep.BaseURL, "/") + "/audio/transcriptions"

	var buf bytes.Buffer
	mp := multipart.NewWriter(&buf)

	// Write the audio file part.
	fw, err := mp.CreateFormFile("file", "audio.webm")
	if err != nil {
		return "", fmt.Errorf("create form file: %w", err)
	}
	if _, err := io.Copy(fw, bytes.NewReader(audio)); err != nil {
		return "", fmt.Errorf("write audio to form: %w", err)
	}

	// Write model field.
	if err := mp.WriteField("model", model); err != nil {
		return "", fmt.Errorf("write model field: %w", err)
	}
	if language != "" {
		if err := mp.WriteField("language", language); err != nil {
			return "", fmt.Errorf("write language field: %w", err)
		}
	}
	mp.Close()

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, &buf)
	if err != nil {
		return "", fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("Content-Type", mp.FormDataContentType())
	if ep.APIKey != "" {
		req.Header.Set("Authorization", "Bearer "+ep.APIKey)
	}

	client := &http.Client{Timeout: 60 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", fmt.Errorf("api request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("api returned %d: %s", resp.StatusCode, string(body))
	}

	var result struct {
		Text string `json:"text"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return "", fmt.Errorf("decode response: %w", err)
	}

	log.Printf("stt: API transcription: %d chars from %s", len(result.Text), ep.BaseURL)
	return result.Text, nil
}

// ── Public interface ──

// Transcribe transcribes audio bytes to text using the configured provider.
func (s *STTService) Transcribe(ctx context.Context, audio []byte) (string, error) {
	settings, err := loadSettings()
	if err != nil {
		return "", fmt.Errorf("stt: load settings: %w", err)
	}
	if !settings.STTEnabled {
		return "", nil
	}

	provider := settings.STTProvider
	model := settings.STTModel
	language := settings.STTLanguage

	switch {
	case provider == "disabled", provider == "browser":
		return "", nil
	case provider == "local":
		return s.transcribeLocal(ctx, audio, language)
	case strings.HasPrefix(provider, "endpoint:"):
		endpointID := provider[len("endpoint:"):]
		return s.transcribeAPI(ctx, audio, endpointID, model, language)
	default:
		return "", fmt.Errorf("stt: unknown provider: %s", provider)
	}
}

func (s *STTService) transcribeLocal(ctx context.Context, audio []byte, language string) (string, error) {
	w := s.getWhisper()
	if w == nil {
		return "", fmt.Errorf("stt: whisper model not available")
	}
	opts := make(map[string]string)
	if language != "" {
		opts["language"] = language
	}
	text, err := w.Transcribe(ctx, audio, opts)
	if err != nil {
		return "", fmt.Errorf("stt: local transcription: %w", err)
	}
	log.Printf("stt: local transcription: %d chars", len(text))
	return text, nil
}

// Stats holds the current STT service state, mirroring get_stats() in Python.
type Stats struct {
	Available   bool   `json:"available"`
	Provider    string `json:"provider"`
	Model       string `json:"model"`
	Language    string `json:"language"`
	ModelLoaded bool   `json:"model_loaded,omitempty"`
	EndpointID  string `json:"endpoint_id,omitempty"`
}

// Stats returns the current service statistics.
func (s *STTService) Stats() Stats {
	settings, err := loadSettings()
	if err != nil {
		return Stats{Available: false, Provider: "disabled"}
	}

	provider := settings.STTProvider
	sttEnabled := settings.STTEnabled
	effectiveProvider := provider
	if !sttEnabled {
		effectiveProvider = "disabled"
	}

	st := Stats{
		Available: s.Available(),
		Provider:  effectiveProvider,
		Model:     settings.STTModel,
		Language:  settings.STTLanguage,
	}

	switch {
	case provider == "local":
		st.ModelLoaded = s.getWhisper() != nil
	case provider == "browser":
		st.Model = "Browser (Web Speech API)"
	case strings.HasPrefix(provider, "endpoint:"):
		st.EndpointID = provider[len("endpoint:"):]
	}

	return st
}

// ── Singleton ──

var (
	globalSTT  *STTService
	globalOnce sync.Once
)

// GetSTTService returns the module-level singleton STTService.
func GetSTTService() *STTService {
	globalOnce.Do(func() {
		globalSTT = New()
	})
	return globalSTT
}
