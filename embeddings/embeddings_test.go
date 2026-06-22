// Unit tests for the embeddings package.
package embeddings

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"
)

// --- ConfigFromEnv ----------------------------------------------------------

func TestConfigFromEnv_AllUnset(t *testing.T) {
	t.Setenv(EnvEmbeddingURL, "")
	t.Setenv(EnvEmbeddingModel, "")
	t.Setenv(EnvEmbeddingAPIKey, "")
	t.Setenv(EnvLLMHost, "")

	cfg := ConfigFromEnv()
	if cfg.URL != "http://localhost:11434/v1/embeddings" {
		t.Errorf("URL = %q, want default Ollama URL", cfg.URL)
	}
	if cfg.Model != defaultModel {
		t.Errorf("Model = %q, want %q", cfg.Model, defaultModel)
	}
	if cfg.APIKey != "" {
		t.Errorf("APIKey = %q, want empty", cfg.APIKey)
	}
}

func TestConfigFromEnv_LLMHostAffectsDefault(t *testing.T) {
	t.Setenv(EnvEmbeddingURL, "")
	t.Setenv(EnvEmbeddingModel, "")
	t.Setenv(EnvEmbeddingAPIKey, "")
	t.Setenv(EnvLLMHost, "10.0.0.7")

	cfg := ConfigFromEnv()
	if !strings.Contains(cfg.URL, "10.0.0.7") {
		t.Errorf("URL = %q, expected to embed LLM_HOST", cfg.URL)
	}
	if !strings.HasSuffix(cfg.URL, ":11434/v1/embeddings") {
		t.Errorf("URL = %q, expected :11434/v1/embeddings suffix", cfg.URL)
	}
}

func TestConfigFromEnv_Explicit(t *testing.T) {
	t.Setenv(EnvEmbeddingURL, "http://example.test:8000/v1/embeddings")
	t.Setenv(EnvEmbeddingModel, "text-embedding-3-small")
	t.Setenv(EnvEmbeddingAPIKey, "sk-test-123")
	t.Setenv(EnvLLMHost, "should-be-ignored")

	cfg := ConfigFromEnv()
	if cfg.URL != "http://example.test:8000/v1/embeddings" {
		t.Errorf("URL = %q", cfg.URL)
	}
	if cfg.Model != "text-embedding-3-small" {
		t.Errorf("Model = %q", cfg.Model)
	}
	if cfg.APIKey != "sk-test-123" {
		t.Errorf("APIKey = %q", cfg.APIKey)
	}
}

// --- NewEmbeddingClient defaults --------------------------------------------

func TestNewEmbeddingClient_FillsDefaults(t *testing.T) {
	c := NewEmbeddingClient(Config{URL: "http://x:1/v1/embeddings"})
	if c.URL() != "http://x:1/v1/embeddings" {
		t.Errorf("URL() = %q", c.URL())
	}
	if c.Model() != defaultModel {
		t.Errorf("Model() = %q, want %q", c.Model(), defaultModel)
	}
	if c.cfg.ConnectTimeout != 3*time.Second {
		t.Errorf("ConnectTimeout = %v", c.cfg.ConnectTimeout)
	}
	if c.cfg.ReadTimeout != 10*time.Second {
		t.Errorf("ReadTimeout = %v", c.cfg.ReadTimeout)
	}
}

func TestNewEmbeddingClient_ZeroURLFallsBackToOllama(t *testing.T) {
	c := NewEmbeddingClient(Config{})
	if !strings.Contains(c.URL(), "localhost:11434") {
		t.Errorf("URL = %q, want fallback to Ollama localhost", c.URL())
	}
}

// --- HTTPEncode ------------------------------------------------------------

// fakeEmbedServer returns a server that mimics an OpenAI-compatible
// embeddings endpoint. It records the request body and Authorization header
// so tests can assert on them.
type fakeEmbedServer struct {
	srv     *httptest.Server
	hits    int
	bodies  []map[string]any
	auths   []string
	dim     int
	batchOK bool
}

func newFakeEmbedServer(t *testing.T, dim int) *fakeEmbedServer {
	t.Helper()
	f := &fakeEmbedServer{dim: dim}
	f.srv = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		f.hits++

		body, _ := io.ReadAll(r.Body)
		var parsed map[string]any
		if err := json.Unmarshal(body, &parsed); err != nil {
			http.Error(w, "bad json", http.StatusBadRequest)
			return
		}
		f.bodies = append(f.bodies, parsed)
		f.auths = append(f.auths, r.Header.Get("Authorization"))

		// Simulate slight out-of-order response for the first request so the
		// sort-by-index path is exercised.
		inputs, _ := parsed["input"].([]any)
		data := make([]map[string]any, 0, len(inputs))
		// Reverse the index ordering for the FIRST batch only.
		reverse := f.hits == 1 && len(inputs) > 1
		for i, in := range inputs {
			idx := i
			if reverse {
				idx = len(inputs) - 1 - i
			}
			_, _ = in.(string) // ignore actual text
			emb := make([]float32, f.dim)
			for j := range emb {
				emb[j] = float32(idx + 1) // unique signal per index
			}
			data = append(data, map[string]any{
				"index":     idx,
				"embedding": emb,
			})
		}
		_ = f.batchOK
		resp := map[string]any{"data": data}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(resp)
	}))
	t.Cleanup(f.srv.Close)
	return f
}

func TestEncode_SendsCorrectRequestAndParsesResponse(t *testing.T) {
	f := newFakeEmbedServer(t, 4)

	c := NewEmbeddingClient(Config{
		URL:            f.srv.URL,
		Model:          "test-model",
		ConnectTimeout: 2 * time.Second,
		ReadTimeout:    5 * time.Second,
	})

	vecs, err := c.Encode(context.Background(), []string{"alpha", "beta", "gamma"}, false)
	if err != nil {
		t.Fatalf("Encode: %v", err)
	}
	if len(vecs) != 3 {
		t.Fatalf("got %d vectors, want 3", len(vecs))
	}
	for i, v := range vecs {
		if len(v) != 4 {
			t.Errorf("vector %d: dim = %d, want 4", i, len(v))
		}
	}

	// After the Encode, dim cache should be populated.
	if d, _ := c.Dimension(context.Background()); d != 4 {
		t.Errorf("Dimension after Encode = %d, want 4", d)
	}

	// Sort-by-index: even though the fake server reverses indices, the
	// returned vectors must match input order (alpha gets index 0 in our
	// fake which we set to len-1-0=2; the encoder must reorder back).
	// First vector's first element should be 1 (input index 0, embedding
	// value = idx+1 = 1).
	if vecs[0][0] != 1 {
		t.Errorf("vecs[0][0] = %v, want 1 (index 0 was reordered back)", vecs[0][0])
	}
	if vecs[2][0] != 3 {
		t.Errorf("vecs[2][0] = %v, want 3 (index 2 was reordered back)", vecs[2][0])
	}

	if len(f.bodies) < 1 || f.bodies[0]["model"] != "test-model" {
		t.Errorf("model not propagated to request: %+v", f.bodies)
	}
}

func TestEncode_SendsBearerAuth(t *testing.T) {
	f := newFakeEmbedServer(t, 4)
	c := NewEmbeddingClient(Config{
		URL:    f.srv.URL,
		Model:  "m",
		APIKey: "sk-secret",
	})

	if _, err := c.Encode(context.Background(), []string{"hi"}, false); err != nil {
		t.Fatalf("Encode: %v", err)
	}
	if len(f.auths) == 0 || f.auths[0] != "Bearer sk-secret" {
		t.Errorf("Authorization header = %q, want %q", f.auths, "Bearer sk-secret")
	}
}

func TestEncode_OmitsAuthWhenNoKey(t *testing.T) {
	f := newFakeEmbedServer(t, 4)
	c := NewEmbeddingClient(Config{URL: f.srv.URL, Model: "m"})

	if _, err := c.Encode(context.Background(), []string{"hi"}, false); err != nil {
		t.Fatalf("Encode: %v", err)
	}
	if len(f.auths) == 0 || f.auths[0] != "" {
		t.Errorf("Authorization header = %q, want empty when no API key", f.auths)
	}
}

func TestEncode_BatchesAt64(t *testing.T) {
	f := newFakeEmbedServer(t, 3)
	c := NewEmbeddingClient(Config{URL: f.srv.URL, Model: "m"})

	inputs := make([]string, 130)
	for i := range inputs {
		inputs[i] = fmt.Sprintf("text-%d", i)
	}
	vecs, err := c.Encode(context.Background(), inputs, false)
	if err != nil {
		t.Fatalf("Encode: %v", err)
	}
	if len(vecs) != 130 {
		t.Errorf("got %d vectors, want 130", len(vecs))
	}
	// 130 inputs / 64 batchSize = ceil(130/64) = 3 batches.
	if f.hits != 3 {
		t.Errorf("expected 3 HTTP calls (batches of 64,64,2), got %d", f.hits)
	}
}

func TestEncode_EmptyInputReturnsEmptySlice(t *testing.T) {
	c := NewEmbeddingClient(Config{URL: "http://localhost:1", Model: "m"})
	vecs, err := c.Encode(context.Background(), nil, true)
	if err != nil {
		t.Fatalf("Encode(nil): %v", err)
	}
	if len(vecs) != 0 {
		t.Errorf("len(vecs) = %d, want 0", len(vecs))
	}

	vecs, err = c.Encode(context.Background(), []string{}, true)
	if err != nil {
		t.Fatalf("Encode([]): %v", err)
	}
	if len(vecs) != 0 {
		t.Errorf("len(vecs) = %d, want 0", len(vecs))
	}
}

func TestEncode_NormalizationToggle(t *testing.T) {
	f := newFakeEmbedServer(t, 5)
	c := NewEmbeddingClient(Config{URL: f.srv.URL, Model: "m"})

	raw, err := c.Encode(context.Background(), []string{"x"}, false)
	if err != nil {
		t.Fatalf("raw: %v", err)
	}
	norm, err := c.Encode(context.Background(), []string{"x"}, true)
	if err != nil {
		t.Fatalf("norm: %v", err)
	}

	rawLen := vectorLen(raw[0])
	if rawLen < 2.2 || rawLen > 2.3 {
		t.Errorf("raw vector length = %v, want ~sqrt(5) (unnormalized fake)", rawLen)
	}
	normLen := vectorLen(norm[0])
	if normLen < 0.999 || normLen > 1.001 {
		t.Errorf("normalized vector length = %v, want 1.0", normLen)
	}
}

func TestEncode_4xxSurfacesAsError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "nope", http.StatusUnauthorized)
	}))
	defer srv.Close()

	c := NewEmbeddingClient(Config{
		URL:         srv.URL,
		Model:       "m",
		APIKey:      "bad",
		ReadTimeout: 2 * time.Second,
	})
	_, err := c.Encode(context.Background(), []string{"hi"}, false)
	if err == nil {
		t.Fatal("expected error on 401, got nil")
	}
	if !strings.Contains(err.Error(), "401") {
		t.Errorf("error %q should mention status 401", err)
	}
}

func TestEncode_5xxSurfacesAsError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "boom", http.StatusInternalServerError)
	}))
	defer srv.Close()

	c := NewEmbeddingClient(Config{URL: srv.URL, Model: "m", ReadTimeout: 2 * time.Second})
	_, err := c.Encode(context.Background(), []string{"hi"}, false)
	if err == nil {
		t.Fatal("expected error on 500, got nil")
	}
}

func TestEncode_ConnectionRefusedWrapsErrEmbeddingUnavailable(t *testing.T) {
	c := NewEmbeddingClient(Config{
		URL:            "http://127.0.0.1:1/v1/embeddings", // nothing listening
		Model:          "m",
		ConnectTimeout: 200 * time.Millisecond,
		ReadTimeout:    500 * time.Millisecond,
	})
	_, err := c.Encode(context.Background(), []string{"hi"}, false)
	if err == nil {
		t.Fatal("expected connection error, got nil")
	}
	if !errors.Is(err, ErrEmbeddingUnavailable) {
		t.Errorf("expected ErrEmbeddingUnavailable in chain, got %v", err)
	}
}

// --- Dimension probing ------------------------------------------------------

func TestDimension_CachesAcrossCalls(t *testing.T) {
	var hits int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		hits++
		resp := map[string]any{
			"data": []map[string]any{
				{"index": 0, "embedding": []float32{0.1, 0.2, 0.3, 0.4}},
			},
		}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()

	c := NewEmbeddingClient(Config{URL: srv.URL, Model: "m"})

	d1, err := c.Dimension(context.Background())
	if err != nil || d1 != 4 {
		t.Fatalf("first Dimension = %d, err=%v", d1, err)
	}
	d2, err := c.Dimension(context.Background())
	if err != nil || d2 != 4 {
		t.Fatalf("second Dimension = %d, err=%v", d2, err)
	}
	d3, err := c.Dimension(context.Background())
	if err != nil || d3 != 4 {
		t.Fatalf("third Dimension = %d, err=%v", d3, err)
	}
	if hits != 1 {
		t.Errorf("expected exactly 1 HTTP call across 3 Dimension probes, got %d", hits)
	}
}

func TestDimension_ConcurrentProbesHappenOnce(t *testing.T) {
	var hits int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Tiny sleep so racing goroutines pile up before any response.
		time.Sleep(20 * time.Millisecond)
		atomic.AddInt32(&hits, 1)
		resp := map[string]any{
			"data": []map[string]any{
				{"index": 0, "embedding": []float32{0.5, 0.6, 0.7}},
			},
		}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()

	c := NewEmbeddingClient(Config{URL: srv.URL, Model: "m"})

	const N = 16
	var wg sync.WaitGroup
	wg.Add(N)
	results := make([]int, N)
	start := make(chan struct{})
	for i := 0; i < N; i++ {
		go func(i int) {
			defer wg.Done()
			<-start
			d, err := c.Dimension(context.Background())
			if err != nil {
				t.Errorf("goroutine %d: %v", i, err)
				return
			}
			results[i] = d
		}(i)
	}
	close(start)
	wg.Wait()

	for i, d := range results {
		if d != 3 {
			t.Errorf("goroutine %d returned dim=%d, want 3", i, d)
		}
	}
	if hits > 1 {
		t.Errorf("expected at most 1 HTTP probe across %d goroutines, got %d", N, hits)
	}
}

func TestDimension_ProbeFailureReturnsError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "boom", http.StatusInternalServerError)
	}))
	defer srv.Close()

	c := NewEmbeddingClient(Config{URL: srv.URL, Model: "m", ReadTimeout: time.Second})
	if _, err := c.Dimension(context.Background()); err == nil {
		t.Fatal("expected error on probe failure, got nil")
	}
}

// --- Persisted endpoint -----------------------------------------------------

func TestLoadPersistedEndpoint_RoundTrip(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "endpoint.json")

	want := PersistedEndpoint{
		URL:    "http://persisted.test:9999/v1/embeddings",
		Model:  "text-embedding-3-large",
		APIKey: "encrypted-blob",
	}
	data, err := json.Marshal(want)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	if err := os.WriteFile(path, data, 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}

	got, err := LoadPersistedEndpoint(path)
	if err != nil {
		t.Fatalf("LoadPersistedEndpoint: %v", err)
	}
	if got.URL != want.URL || got.Model != want.Model || got.APIKey != want.APIKey {
		t.Errorf("got %+v, want %+v", got, want)
	}
}

func TestLoadPersistedEndpoint_MissingFileReturnsEmpty(t *testing.T) {
	got, err := LoadPersistedEndpoint(filepath.Join(t.TempDir(), "does-not-exist.json"))
	if err != nil {
		t.Fatalf("expected nil error for missing file, got %v", err)
	}
	if got.URL != "" {
		t.Errorf("expected empty URL, got %q", got.URL)
	}
}

func TestLoadPersistedEndpoint_EmptyPathReturnsEmpty(t *testing.T) {
	got, err := LoadPersistedEndpoint("")
	if err != nil {
		t.Fatalf("expected nil error for empty path, got %v", err)
	}
	if got.URL != "" {
		t.Errorf("expected empty URL, got %q", got.URL)
	}
}

func TestLoadPersistedEndpoint_MalformedReturnsParseError(t *testing.T) {
	path := filepath.Join(t.TempDir(), "bad.json")
	if err := os.WriteFile(path, []byte("{not json"), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}
	_, err := LoadPersistedEndpoint(path)
	if err == nil {
		t.Fatal("expected parse error, got nil")
	}
}

func TestLoadPersistedEndpoint_EmptyURLEqualsAbsent(t *testing.T) {
	path := filepath.Join(t.TempDir(), "no-url.json")
	if err := os.WriteFile(path, []byte(`{"model":"m"}`), 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}
	got, err := LoadPersistedEndpoint(path)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got.URL != "" {
		t.Errorf("URL = %q, want empty (treated as absent)", got.URL)
	}
}

// --- FastEmbed stub ---------------------------------------------------------

func TestFastEmbedClient_WithoutEnvVarReturnsError(t *testing.T) {
	t.Setenv(EnvUseFastEmbed, "")
	_, err := NewFastEmbedClient("")
	if err == nil {
		t.Fatal("expected error, got nil")
	}
	if !errors.Is(err, ErrEmbeddingUnavailable) {
		t.Errorf("expected ErrEmbeddingUnavailable, got %v", err)
	}
}

func TestFastEmbedClient_WithEnvVarReturnsStub(t *testing.T) {
	t.Setenv(EnvUseFastEmbed, "1")
	fe, err := NewFastEmbedClient("custom-model")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if fe.Model() != "custom-model" {
		t.Errorf("Model = %q, want custom-model", fe.Model())
	}
	if fe.URL() != "local://fastembed" {
		t.Errorf("URL = %q, want local://fastembed", fe.URL())
	}
	if _, err := fe.Dimension(context.Background()); !errors.Is(err, ErrEmbeddingUnavailable) {
		t.Errorf("Dimension: expected ErrEmbeddingUnavailable, got %v", err)
	}
	if _, err := fe.Encode(context.Background(), []string{"x"}, false); !errors.Is(err, ErrEmbeddingUnavailable) {
		t.Errorf("Encode: expected ErrEmbeddingUnavailable, got %v", err)
	}
}

func TestFastEmbedClient_DefaultsFromEnv(t *testing.T) {
	t.Setenv(EnvUseFastEmbed, "1")
	t.Setenv(EnvFastEmbedModel, "BAAI/bge-small-en-v1.5")
	fe, err := NewFastEmbedClient("")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if fe.Model() != "BAAI/bge-small-en-v1.5" {
		t.Errorf("Model = %q, want BAAI/bge-small-en-v1.5", fe.Model())
	}
}

// --- Latch / GetEmbeddingClient --------------------------------------------

func TestLatch_ResetAndSet(t *testing.T) {
	SetHTTPDown()
	if !IsHTTPDown() {
		t.Fatal("latch should be down after SetHTTPDown")
	}
	ResetHTTPEmbedState()
	if IsHTTPDown() {
		t.Fatal("latch should be cleared after ResetHTTPEmbedState")
	}
}

func TestGetEmbeddingClient_HTTPUp(t *testing.T) {
	ResetHTTPEmbedState()
	t.Setenv(EnvEmbeddingPersist, "")
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		resp := map[string]any{
			"data": []map[string]any{
				{"index": 0, "embedding": []float32{1, 2, 3, 4, 5}},
			},
		}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()

	t.Setenv(EnvEmbeddingURL, srv.URL)
	t.Setenv(EnvEmbeddingModel, "m")
	t.Setenv(EnvEmbeddingAPIKey, "")

	client, kind, err := GetEmbeddingClient(context.Background())
	if err != nil {
		t.Fatalf("GetEmbeddingClient: %v", err)
	}
	if kind != "http" {
		t.Errorf("kind = %q, want http", kind)
	}
	ec, ok := client.(*EmbeddingClient)
	if !ok {
		t.Fatalf("expected *EmbeddingClient, got %T", client)
	}
	if d, _ := ec.Dimension(context.Background()); d != 5 {
		t.Errorf("dim = %d, want 5", d)
	}
	if IsHTTPDown() {
		t.Errorf("latch should NOT be down on success")
	}
}

func TestGetEmbeddingClient_HTTPDownTripsLatchAndFallsBack(t *testing.T) {
	ResetHTTPEmbedState()
	t.Setenv(EnvEmbeddingPersist, "")
	t.Setenv(EnvEmbeddingURL, "http://127.0.0.1:1/v1/embeddings")
	t.Setenv(EnvEmbeddingModel, "m")
	t.Setenv(EnvUseFastEmbed, "1")
	t.Setenv(EnvFastEmbedModel, "test-fastembed")

	_, kind, err := GetEmbeddingClient(context.Background())
	if err != nil {
		t.Fatalf("GetEmbeddingClient: %v", err)
	}
	if kind != "fastembed" {
		t.Errorf("kind = %q, want fastembed", kind)
	}
	if !IsHTTPDown() {
		t.Errorf("latch should be down after HTTP failure")
	}
	ResetHTTPEmbedState()
}

func TestGetEmbeddingClient_LatchedSkipsHTTPProbe(t *testing.T) {
	ResetHTTPEmbedState()
	t.Setenv(EnvEmbeddingPersist, "")

	var httpHits int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		httpHits++
		resp := map[string]any{
			"data": []map[string]any{
				{"index": 0, "embedding": []float32{1, 2, 3}},
			},
		}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()

	t.Setenv(EnvEmbeddingURL, srv.URL)
	t.Setenv(EnvEmbeddingModel, "m")
	t.Setenv(EnvUseFastEmbed, "1")
	t.Setenv(EnvFastEmbedModel, "x")

	// Trip the latch so GetEmbeddingClient goes straight to FastEmbed.
	SetHTTPDown()
	defer ResetHTTPEmbedState()

	_, kind, err := GetEmbeddingClient(context.Background())
	if err != nil {
		t.Fatalf("GetEmbeddingClient: %v", err)
	}
	if kind != "fastembed" {
		t.Errorf("kind = %q, want fastembed", kind)
	}
	if httpHits != 0 {
		t.Errorf("expected 0 HTTP hits when latched, got %d", httpHits)
	}
}

func TestGetEmbeddingClient_PersistedEndpointOverridesEnv(t *testing.T) {
	ResetHTTPEmbedState()

	var srvHits int
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		srvHits++
		resp := map[string]any{
			"data": []map[string]any{
				{"index": 0, "embedding": []float32{0.1, 0.2, 0.3, 0.4}},
			},
		}
		_ = json.NewEncoder(w).Encode(resp)
	}))
	defer srv.Close()

	dir := t.TempDir()
	path := filepath.Join(dir, "endpoint.json")
	body, _ := json.Marshal(PersistedEndpoint{
		URL:   srv.URL,
		Model: "persisted-model",
	})
	if err := os.WriteFile(path, body, 0o600); err != nil {
		t.Fatalf("write: %v", err)
	}

	t.Setenv(EnvEmbeddingPersist, path)
	// Set env URL to something unreachable to prove the persisted one wins.
	t.Setenv(EnvEmbeddingURL, "http://127.0.0.1:1/v1/embeddings")
	t.Setenv(EnvEmbeddingModel, "env-model")

	client, kind, err := GetEmbeddingClient(context.Background())
	if err != nil {
		t.Fatalf("GetEmbeddingClient: %v", err)
	}
	if kind != "http" {
		t.Errorf("kind = %q, want http (persisted endpoint must override env)", kind)
	}
	if srvHits != 1 {
		t.Errorf("persisted server hits = %d, want 1", srvHits)
	}
	ec := client.(*EmbeddingClient)
	if ec.Model() != "persisted-model" {
		t.Errorf("Model = %q, want persisted-model", ec.Model())
	}
	ResetHTTPEmbedState()
}

func TestGetEmbeddingClient_AllDownReturnsError(t *testing.T) {
	ResetHTTPEmbedState()
	t.Setenv(EnvEmbeddingPersist, "")
	t.Setenv(EnvEmbeddingURL, "http://127.0.0.1:1/v1/embeddings")
	t.Setenv(EnvEmbeddingModel, "m")
	t.Setenv(EnvUseFastEmbed, "") // fastembed unavailable in Go port

	_, _, err := GetEmbeddingClient(context.Background())
	if err == nil {
		t.Fatal("expected error when both backends fail, got nil")
	}
	if !errors.Is(err, ErrEmbeddingUnavailable) {
		t.Errorf("expected ErrEmbeddingUnavailable, got %v", err)
	}
	ResetHTTPEmbedState()
}

// --- helpers ----------------------------------------------------------------

func vectorLen(v []float32) float64 {
	var sum float64
	for _, x := range v {
		sum += float64(x) * float64(x)
	}
	return math.Sqrt(sum)
}

// atomicAdd is no longer used; the concurrent test uses sync/atomic
// directly. The CAS-based shim was removed in favor of the stdlib counter.
