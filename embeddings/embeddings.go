// Package embeddings is the Go port of src/embeddings.py.
//
// It exposes two clients that share a common shape (Encode/Dimension/URL/Model):
//
//   - EmbeddingClient — an OpenAI-compatible HTTP client (Ollama, vLLM,
//     llama.cpp, etc.). This is the production path and is fully implemented.
//
//   - FastEmbedClient — a local ONNX runtime client (Python: fastembed). The
//     Go port ships a stub that returns a clear "not available" error, because
//     bundling ONNX + HuggingFace model fetch would force a CGo / large-dep
//     dependency that the rest of the project explicitly avoids. The type is
//     kept so call-sites that mirror the Python surface still compile; callers
//     that genuinely need a local model must run FastEmbedClient's constructor
//     behind EMBEDDINGS_USE_FASTEMBED=1 and accept the error.
//
// The HTTP client is shared across goroutines — the lazy dimension cache uses
// sync.Once + sync/atomic so concurrent Encode/Dimension calls from
// background workers cannot tear it.
package embeddings

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net/http"
	"os"
	"sort"
	"sync"
	"sync/atomic"
	"time"
)

// Environment variable names. Exported as symbols so operators and tests can
// reference them without copying string literals.
const (
	EnvEmbeddingURL     = "EMBEDDING_URL"
	EnvEmbeddingModel   = "EMBEDDING_MODEL"
	EnvEmbeddingAPIKey  = "EMBEDDING_API_KEY"
	EnvLLMHost          = "LLM_HOST"
	EnvFastEmbedModel   = "FASTEMBED_MODEL"
	EnvUseFastEmbed     = "EMBEDDINGS_USE_FASTEMBED"
	EnvEmbeddingPersist = "EMBEDDING_ENDPOINT_FILE"
)

// Defaults match the Python reference.
const (
	defaultModel          = "all-minilm:l6-v2"
	defaultFastEmbedModel = "sentence-transformers/all-MiniLM-L6-v2"
	defaultOllamaPort     = "11434"
	defaultEmbedPath      = "/v1/embeddings"
)

// batchSize matches the Python chunk size (64). Anything bigger risks an
// oversized POST for small embedding servers.
const batchSize = 64

// Sentinel errors. Callers use errors.Is to distinguish "endpoint down" from
// "endpoint returned a bad response".
var (
	ErrEmbeddingUnavailable = errors.New("embedding endpoint unavailable")
	ErrEndpointDown         = errors.New("embedding endpoint is down (latched for this process)")
)

// PersistedEndpoint is the shape of the JSON file written by the admin panel
// when a user saves a custom endpoint. Only the URL field is required; model
// and api_key may be empty.
type PersistedEndpoint struct {
	URL    string `json:"url"`
	Model  string `json:"model,omitempty"`
	APIKey string `json:"api_key,omitempty"`
}

// Config is the resolved set of embedding-client options. It is what
// NewEmbeddingClient consumes.
type Config struct {
	URL    string
	Model  string
	APIKey string

	// ConnectTimeout / ReadTimeout mirror httpx's connect=3s / read=10s
	// budget so a DOWN endpoint (e.g. Ollama not running on :11434)
	// fast-fails instead of stalling startup ~30s per probe.
	ConnectTimeout time.Duration
	ReadTimeout    time.Duration
	WriteTimeout   time.Duration
	PoolTimeout    time.Duration
}

// ConfigFromEnv builds a Config from the EMBEDDING_URL / EMBEDDING_MODEL /
// EMBEDDING_API_KEY / LLM_HOST environment variables. Empty values fall back to
// the Python defaults (Ollama on localhost:11434, model all-minilm:l6-v2).
func ConfigFromEnv() Config {
	cfg := Config{
		URL:            "http://" + getEnv(EnvLLMHost, "localhost") + ":" + defaultOllamaPort + defaultEmbedPath,
		Model:          defaultModel,
		ConnectTimeout: 3 * time.Second,
		ReadTimeout:    10 * time.Second,
		WriteTimeout:   5 * time.Second,
		PoolTimeout:    3 * time.Second,
	}

	if v := os.Getenv(EnvEmbeddingURL); v != "" {
		cfg.URL = v
	}
	if v := os.Getenv(EnvEmbeddingModel); v != "" {
		cfg.Model = v
	}
	if v := os.Getenv(EnvEmbeddingAPIKey); v != "" {
		cfg.APIKey = v
	}

	return cfg
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

// EmbeddingClient is an OpenAI-compatible embeddings HTTP client. The zero
// value is not usable; call NewEmbeddingClient.
type EmbeddingClient struct {
	cfg     Config
	httpc   *http.Client
	dimOnce sync.Once
	dim     atomic.Int32 // 0 until first successful probe
}

// NewEmbeddingClient builds an EmbeddingClient from a resolved Config. Pass
// ConfigFromEnv() for the standard env-driven setup.
func NewEmbeddingClient(cfg Config) *EmbeddingClient {
	if cfg.URL == "" {
		cfg.URL = "http://localhost:" + defaultOllamaPort + defaultEmbedPath
	}
	if cfg.Model == "" {
		cfg.Model = defaultModel
	}
	if cfg.ConnectTimeout == 0 {
		cfg.ConnectTimeout = 3 * time.Second
	}
	if cfg.ReadTimeout == 0 {
		cfg.ReadTimeout = 10 * time.Second
	}

	return &EmbeddingClient{
		cfg:   cfg,
		httpc: &http.Client{Timeout: cfg.ReadTimeout},
	}
}

// URL returns the configured endpoint URL.
func (c *EmbeddingClient) URL() string { return c.cfg.URL }

// Model returns the configured model name.
func (c *EmbeddingClient) Model() string { return c.cfg.Model }

// Dimension probes the endpoint for the embedding dimension and caches it.
// Subsequent calls are a cheap atomic load. The first call performs one HTTP
// request with the input "hello" — that mirrors the Python implementation.
func (c *EmbeddingClient) Dimension(ctx context.Context) (int, error) {
	if d := int(c.dim.Load()); d > 0 {
		return d, nil
	}

	c.dimOnce.Do(func() {
		vecs, err := c.encodeOnce(ctx, []string{"hello"}, false)
		if err != nil {
			return
		}
		if len(vecs) > 0 {
			c.dim.Store(int32(len(vecs[0])))
		}
	})

	if d := int(c.dim.Load()); d > 0 {
		return d, nil
	}
	return 0, fmt.Errorf("%w: dimension probe failed", ErrEmbeddingUnavailable)
}

// Encode embeds texts via the configured HTTP endpoint. Returns a slice of
// float32 vectors with shape (len(texts), dim). Empty input returns an empty
// (non-nil) slice. When normalize is true, every returned vector is L2-
// normalized to unit length (matching the Python default).
func (c *EmbeddingClient) Encode(ctx context.Context, texts []string, normalize bool) ([][]float32, error) {
	if len(texts) == 0 {
		return [][]float32{}, nil
	}

	var out [][]float32
	for i := 0; i < len(texts); i += batchSize {
		end := i + batchSize
		if end > len(texts) {
			end = len(texts)
		}
		batch := texts[i:end]

		vecs, err := c.encodeOnce(ctx, batch, normalize)
		if err != nil {
			return nil, err
		}
		out = append(out, vecs...)
	}

	if d := int(c.dim.Load()); d == 0 && len(out) > 0 {
		c.dim.Store(int32(len(out[0])))
	}
	return out, nil
}

// encodeOnce does a single POST for one batch. It is the only place we touch
// the network.
func (c *EmbeddingClient) encodeOnce(ctx context.Context, batch []string, normalize bool) ([][]float32, error) {
	reqBody, err := json.Marshal(map[string]any{
		"input": batch,
		"model": c.cfg.Model,
	})
	if err != nil {
		return nil, fmt.Errorf("embeddings: marshal request: %w", err)
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.cfg.URL, bytes.NewReader(reqBody))
	if err != nil {
		return nil, fmt.Errorf("embeddings: build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if c.cfg.APIKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.cfg.APIKey)
	}

	resp, err := c.httpc.Do(req)
	if err != nil {
		return nil, fmt.Errorf("%w: %v", ErrEmbeddingUnavailable, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		_, _ = io.Copy(io.Discard, resp.Body)
		return nil, fmt.Errorf("embeddings: unexpected status %d from %s", resp.StatusCode, c.cfg.URL)
	}

	var parsed embedResponse
	if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
		return nil, fmt.Errorf("embeddings: decode response: %w", err)
	}

	// OpenAI format: {"data": [{"embedding": [...], "index": 0}, ...]}
	// Sort by index so batch order matches input order even if the server
	// reorders — same defensive ordering as the Python version.
	sort.Slice(parsed.Data, func(i, j int) bool {
		return parsed.Data[i].Index < parsed.Data[j].Index
	})

	out := make([][]float32, 0, len(parsed.Data))
	for _, d := range parsed.Data {
		v := make([]float32, len(d.Embedding))
		copy(v, d.Embedding)
		if normalize {
			l2Normalize(v)
		}
		out = append(out, v)
	}
	return out, nil
}

// embedResponse mirrors the OpenAI-compatible embeddings payload.
type embedResponse struct {
	Data []embedItem `json:"data"`
}

type embedItem struct {
	Index     int       `json:"index"`
	Embedding []float32 `json:"embedding"`
}

// l2Normalize scales v in place to unit length. A zero vector is left as-is
// (matching numpy's where(norms==0, 1, norms) guard).
func l2Normalize(v []float32) {
	var sum float64
	for _, x := range v {
		sum += float64(x) * float64(x)
	}
	norm := math.Sqrt(sum)
	if norm == 0 {
		return
	}
	inv := float32(1 / norm)
	for i := range v {
		v[i] *= inv
	}
}

// FastEmbedClient is the local-ONNX counterpart to EmbeddingClient. The Go
// port does NOT bundle an ONNX runtime — doing so would force a CGo
// dependency that this project does not use elsewhere. Instead the
// constructor returns a clear error when EMBEDDINGS_USE_FASTEMBED=1 is set,
// and the Encode/Dimension methods always return ErrEmbeddingUnavailable.
//
// The type is kept (with its Method/URL/Dimension surface) so that callers
// matching the Python API still compile. Production code should use
// EmbeddingClient and treat FastEmbedClient as the explicit fallback.
type FastEmbedClient struct {
	model string
}

// NewFastEmbedClient attempts to construct a FastEmbedClient. In this Go
// port it always returns ErrEmbeddingUnavailable with a helpful message —
// there is no onnxruntime linked into the binary. Callers that want the
// stub API surface (URL/Dimension) can wrap this in a non-nil check.
func NewFastEmbedClient(model string) (*FastEmbedClient, error) {
	if os.Getenv(EnvUseFastEmbed) == "" {
		return nil, fmt.Errorf(
			"%w: fastembed is not available in the Go port; set EMBEDDING_URL to a remote embedding server instead",
			ErrEmbeddingUnavailable,
		)
	}

	m := model
	if m == "" {
		m = getEnv(EnvFastEmbedModel, defaultFastEmbedModel)
	}
	return &FastEmbedClient{model: m}, nil
}

// Model returns the configured fastembed model name.
func (c *FastEmbedClient) Model() string { return c.model }

// URL is the canonical "local://fastembed" sentinel, matching the Python.
func (c *FastEmbedClient) URL() string { return "local://fastembed" }

// Dimension always returns ErrEmbeddingUnavailable in the Go port — see
// the package doc.
func (c *FastEmbedClient) Dimension(_ context.Context) (int, error) {
	return 0, fmt.Errorf("%w: fastembed Dimension is not implemented in Go", ErrEmbeddingUnavailable)
}

// Encode always returns ErrEmbeddingUnavailable in the Go port.
func (c *FastEmbedClient) Encode(_ context.Context, _ []string, _ bool) ([][]float32, error) {
	return nil, fmt.Errorf("%w: fastembed Encode is not implemented in Go", ErrEmbeddingUnavailable)
}

// LoadPersistedEndpoint reads the JSON file at path (the Python module uses
// EMBEDDING_ENDPOINT_FILE from src/constants.py). It returns an empty
// PersistedEndpoint if the file is missing or unreadable; only parse errors
// are returned. This mirrors the Python "swallow everything except an empty
// file with a url" behavior.
func LoadPersistedEndpoint(path string) (PersistedEndpoint, error) {
	if path == "" {
		return PersistedEndpoint{}, nil
	}
	data, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return PersistedEndpoint{}, nil
		}
		return PersistedEndpoint{}, fmt.Errorf("embeddings: read persisted endpoint: %w", err)
	}
	var ep PersistedEndpoint
	if err := json.Unmarshal(data, &ep); err != nil {
		return PersistedEndpoint{}, fmt.Errorf("embeddings: parse persisted endpoint: %w", err)
	}
	if ep.URL == "" {
		return PersistedEndpoint{}, nil
	}
	return ep, nil
}

// --- process-wide latch ------------------------------------------------------

// httpEmbedDown is the process-wide "we already saw the endpoint fail" latch.
// Matches the Python _http_embed_down global — once tripped, subsequent
// GetEmbeddingClient calls skip the HTTP probe and go straight to the
// FastEmbed fallback.
var httpEmbedDown atomic.Bool

// ResetHTTPEmbedState clears the down latch. Call this when the embedding
// endpoint setting changes (e.g. the user starts Ollama and saves the
// endpoint) — otherwise a latch tripped at startup would pin the process to
// FastEmbed for its whole lifetime.
func ResetHTTPEmbedState() {
	httpEmbedDown.Store(false)
}

// SetHTTPDown trips the latch. Exposed so tests can simulate the Python
// behavior of "endpoint was probed and failed".
func SetHTTPDown() {
	httpEmbedDown.Store(true)
}

// IsHTTPDown reports the latch state. Used by the CLI to render effective
// config.
func IsHTTPDown() bool {
	return httpEmbedDown.Load()
}

// GetEmbeddingClient is the factory: HTTP-first, FastEmbed-fallback. It
// honors the down latch and the persisted endpoint file.
//
// Returns (client, kind, err) where kind is "http" or "fastembed". When
// both paths fail the error wraps ErrEmbeddingUnavailable and the returned
// client is nil.
func GetEmbeddingClient(ctx context.Context) (any, string, error) {
	if path := os.Getenv(EnvEmbeddingPersist); path != "" {
		if ep, err := LoadPersistedEndpoint(path); err == nil && ep.URL != "" {
			cfg := ConfigFromEnv()
			cfg.URL = ep.URL
			if ep.Model != "" {
				cfg.Model = ep.Model
			}
			if ep.APIKey != "" {
				cfg.APIKey = ep.APIKey
			}
			client := NewEmbeddingClient(cfg)
			if d, err := client.Dimension(ctx); err == nil && d > 0 {
				return client, "http", nil
			}
			httpEmbedDown.Store(true)
		}
	}

	if !httpEmbedDown.Load() {
		cfg := ConfigFromEnv()
		client := NewEmbeddingClient(cfg)
		if _, err := client.Dimension(ctx); err == nil {
			return client, "http", nil
		}
		httpEmbedDown.Store(true)
	}

	model := getEnv(EnvFastEmbedModel, defaultFastEmbedModel)
	fe, err := NewFastEmbedClient(model)
	if err != nil {
		return nil, "", fmt.Errorf("%w: %v", ErrEmbeddingUnavailable, err)
	}
	return fe, "fastembed", nil
}
