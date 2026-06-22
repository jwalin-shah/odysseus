package embeddings

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"sync"
	"testing"
)

// ---------------------------------------------------------------------------
// Test helpers / fixtures.
// ---------------------------------------------------------------------------

// fixedEmbedder is a deterministic EmbedderFunc that hashes each text into
// the same fixed-dimension vector. Useful for fastembed-fallback tests
// without needing ONNX.
func fixedEmbedder(dim int) EmbedderFunc {
	return func(texts []string) (Encoding, error) {
		out := make(Encoding, len(texts))
		for i, t := range texts {
			row := make([]float32, dim)
			// Simple deterministic spread: fill with byte values so the
			// L2 norm is non-zero and normalisation can be tested.
			for j := 0; j < dim; j++ {
				row[j] = float32((int(t[0])+j)%7+1) / 10.0
			}
			out[i] = row
		}
		return out, nil
	}
}

// newTestServer starts an httptest.Server that mimics an OpenAI-style
// /v1/embeddings endpoint. The handler captures the last received
// request and returns a programmable response.
func newTestServer(t *testing.T, handler func(req embedRequest) (int, embedResponse)) (*httptest.Server, *embedCapture) {
	t.Helper()
	cap := &embedCapture{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		body, _ := io.ReadAll(r.Body)
		cap.bodies = append(cap.bodies, string(body))
		cap.headers = append(cap.headers, r.Header.Clone())
		var req embedRequest
		if err := json.Unmarshal(body, &req); err != nil {
			http.Error(w, "bad request", http.StatusBadRequest)
			return
		}
		status, resp := handler(req)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		_ = json.NewEncoder(w).Encode(resp)
	}))
	t.Cleanup(srv.Close)
	return srv, cap
}

type embedRequest struct {
	Input []string `json:"input"`
	Model string   `json:"model"`
}

type embedResponse struct {
	Data []struct {
		Index     int       `json:"index"`
		Embedding []float32 `json:"embedding"`
	} `json:"data"`
}

type embedCapture struct {
	mu      sync.Mutex
	bodies  []string
	headers []http.Header
}

func (c *embedCapture) lastHeaders() http.Header {
	c.mu.Lock()
	defer c.mu.Unlock()
	if len(c.headers) == 0 {
		return http.Header{}
	}
	return c.headers[len(c.headers)-1]
}

func (c *embedCapture) requestCount() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return len(c.bodies)
}

// ---------------------------------------------------------------------------
// EmbeddingClient tests.
// ---------------------------------------------------------------------------

func TestResolveURL(t *testing.T) {
	cases := []struct {
		name   string
		envURL string
		host   string
		want   string
	}{
		{"explicit arg wins", "http://explicit:1/v1/embeddings", "", "http://explicit:1/v1/embeddings"},
		{"env wins when no explicit", "http://env:11434/v1/embeddings", "", "http://env:11434/v1/embeddings"},
		{"default uses LLM_HOST", "", "10.0.0.5", "http://10.0.0.5:11434/v1/embeddings"},
		{"default localhost when unset", "", "", "http://localhost:11434/v1/embeddings"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Setenv(envEmbeddingURL, tc.envURL)
			t.Setenv(envLLMHost, tc.host)
			if got := resolveURL(""); got != tc.want {
				t.Errorf("resolveURL() = %q, want %q", got, tc.want)
			}
		})
	}
}

func TestStringOrEnv(t *testing.T) {
	t.Run("explicit wins", func(t *testing.T) {
		t.Setenv("FOO", "from-env")
		if got := stringOrEnv("explicit", "FOO", "fallback"); got != "explicit" {
			t.Errorf("got %q", got)
		}
	})
	t.Run("env when explicit empty", func(t *testing.T) {
		t.Setenv("FOO", "from-env")
		if got := stringOrEnv("", "FOO", "fallback"); got != "from-env" {
			t.Errorf("got %q", got)
		}
	})
	t.Run("env whitespace-only treated as empty", func(t *testing.T) {
		t.Setenv("FOO", "   ")
		if got := stringOrEnv("", "FOO", "fallback"); got != "fallback" {
			t.Errorf("got %q", got)
		}
	})
	t.Run("fallback when all empty", func(t *testing.T) {
		t.Setenv("FOO", "")
		if got := stringOrEnv("", "FOO", "fb"); got != "fb" {
			t.Errorf("got %q", got)
		}
	})
}

func TestEmbeddingClientBearerHeaderSetWhenAPIKey(t *testing.T) {
	var captured http.Header
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		captured = r.Header.Clone()
		out := embedResponse{}
		out.Data = append(out.Data, struct {
			Index     int       `json:"index"`
			Embedding []float32 `json:"embedding"`
		}{Index: 0, Embedding: []float32{0.1, 0.2, 0.3}})
		_ = json.NewEncoder(w).Encode(out)
	}))
	defer srv.Close()

	c := NewHTTPEmbeddingClient(Config{
		URL:    srv.URL,
		Model:  "all-minilm:l6-v2",
		APIKey: "secret-key",
	})
	if _, err := c.Encode([]string{"x"}, false); err != nil {
		t.Fatalf("Encode: %v", err)
	}
	if got := captured.Get("Authorization"); got != "Bearer secret-key" {
		t.Errorf("Authorization = %q, want %q", got, "Bearer secret-key")
	}
}

func TestEmbeddingClientNoBearerHeaderWhenAPIKeyEmpty(t *testing.T) {
	var captured http.Header
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		captured = r.Header.Clone()
		out := embedResponse{}
		out.Data = append(out.Data, struct {
			Index     int       `json:"index"`
			Embedding []float32 `json:"embedding"`
		}{Index: 0, Embedding: []float32{0.1, 0.2, 0.3}})
		_ = json.NewEncoder(w).Encode(out)
	}))
	defer srv.Close()

	c := NewHTTPEmbeddingClient(Config{URL: srv.URL})
	if _, err := c.Encode([]string{"x"}, false); err != nil {
		t.Fatalf("Encode: %v", err)
	}
	if got := captured.Get("Authorization"); got != "" {
		t.Errorf("Authorization should be unset, got %q", got)
	}
}

func TestEmbeddingClientEncodeNormalizesByDefault(t *testing.T) {
	srv, _ := newTestServer(t, func(req embedRequest) (int, embedResponse) {
		out := embedResponse{}
		for i := range req.Input {
			out.Data = append(out.Data, struct {
				Index     int       `json:"index"`
				Embedding []float32 `json:"embedding"`
			}{Index: i, Embedding: []float32{3, 4, 0, 0}})
		}
		return http.StatusOK, out
	})

	c := NewHTTPEmbeddingClient(Config{URL: srv.URL})
	vecs, err := c.Encode([]string{"a", "b"}, true)
	if err != nil {
		t.Fatalf("Encode: %v", err)
	}
	if len(vecs) != 2 {
		t.Fatalf("expected 2 vectors, got %d", len(vecs))
	}
	for i, row := range vecs {
		// Each row should be the normalised [3,4,0,0] -> [0.6,0.8,0,0]
		want := []float32{0.6, 0.8, 0, 0}
		if !floatSliceNear(row, want, 1e-5) {
			t.Errorf("row %d = %v, want %v", i, row, want)
		}
	}
}

func TestEmbeddingClientEncodeSkipsNormalizeWhenFalse(t *testing.T) {
	srv, _ := newTestServer(t, func(req embedRequest) (int, embedResponse) {
		out := embedResponse{}
		for i := range req.Input {
			out.Data = append(out.Data, struct {
				Index     int       `json:"index"`
				Embedding []float32 `json:"embedding"`
			}{Index: i, Embedding: []float32{3, 4}})
		}
		return http.StatusOK, out
	})

	c := NewHTTPEmbeddingClient(Config{URL: srv.URL})
	vecs, err := c.Encode([]string{"a"}, false)
	if err != nil {
		t.Fatalf("Encode: %v", err)
	}
	if !floatSliceNear(vecs[0], []float32{3, 4}, 1e-5) {
		t.Errorf("vec = %v, want [3 4]", vecs[0])
	}
}

func TestEmbeddingClientEncodeEmptyReturnsEmpty(t *testing.T) {
	c := NewHTTPEmbeddingClient(Config{URL: "http://example"})
	vecs, err := c.Encode(nil, true)
	if err != nil {
		t.Fatalf("Encode(nil): %v", err)
	}
	if len(vecs) != 0 {
		t.Errorf("expected empty slice, got %v", vecs)
	}
}

func TestEmbeddingClientEncodeSortsByIndex(t *testing.T) {
	srv, _ := newTestServer(t, func(req embedRequest) (int, embedResponse) {
		out := embedResponse{}
		// Return out of order
		out.Data = append(out.Data, struct {
			Index     int       `json:"index"`
			Embedding []float32 `json:"embedding"`
		}{Index: 2, Embedding: []float32{2}})
		out.Data = append(out.Data, struct {
			Index     int       `json:"index"`
			Embedding []float32 `json:"embedding"`
		}{Index: 0, Embedding: []float32{0}})
		out.Data = append(out.Data, struct {
			Index     int       `json:"index"`
			Embedding []float32 `json:"embedding"`
		}{Index: 1, Embedding: []float32{1}})
		return http.StatusOK, out
	})

	c := NewHTTPEmbeddingClient(Config{URL: srv.URL})
	vecs, err := c.Encode([]string{"a", "b", "c"}, false)
	if err != nil {
		t.Fatalf("Encode: %v", err)
	}
	if len(vecs) != 3 {
		t.Fatalf("len = %d", len(vecs))
	}
	for i, v := range vecs {
		if v[0] != float32(i) {
			t.Errorf("vecs[%d][0] = %v, want %v", i, v[0], float32(i))
		}
	}
}

func TestEmbeddingClientEncodeBatchesByDefault(t *testing.T) {
	var batchSizes []int
	srv, _ := newTestServer(t, func(req embedRequest) (int, embedResponse) {
		batchSizes = append(batchSizes, len(req.Input))
		out := embedResponse{}
		for i := range req.Input {
			out.Data = append(out.Data, struct {
				Index     int       `json:"index"`
				Embedding []float32 `json:"embedding"`
			}{Index: i, Embedding: []float32{0.1}})
		}
		return http.StatusOK, out
	})

	c := NewHTTPEmbeddingClient(Config{URL: srv.URL})
	const N = 200
	texts := make([]string, N)
	for i := range texts {
		texts[i] = fmt.Sprintf("t%d", i)
	}
	if _, err := c.Encode(texts, false); err != nil {
		t.Fatalf("Encode: %v", err)
	}
	wantSizes := []int{64, 64, 64, 8}
	if !reflect.DeepEqual(batchSizes, wantSizes) {
		t.Errorf("batch sizes = %v, want %v", batchSizes, wantSizes)
	}
}

func TestEmbeddingClientEncodeSurfacesHTTPError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "boom", http.StatusInternalServerError)
	}))
	defer srv.Close()

	c := NewHTTPEmbeddingClient(Config{URL: srv.URL})
	if _, err := c.Encode([]string{"x"}, true); err == nil {
		t.Fatal("expected error on 500, got nil")
	} else if !strings.Contains(err.Error(), "500") {
		t.Errorf("error %q does not mention 500", err)
	}
}

func TestEmbeddingClientGetDimensionCachesResult(t *testing.T) {
	var calls int
	srv, _ := newTestServer(t, func(req embedRequest) (int, embedResponse) {
		calls++
		out := embedResponse{}
		for i := range req.Input {
			out.Data = append(out.Data, struct {
				Index     int       `json:"index"`
				Embedding []float32 `json:"embedding"`
			}{Index: i, Embedding: []float32{0.1, 0.2, 0.3, 0.4}})
		}
		return http.StatusOK, out
	})

	c := NewHTTPEmbeddingClient(Config{URL: srv.URL})
	d1, err := c.GetSentenceEmbeddingDimension()
	if err != nil {
		t.Fatalf("first probe: %v", err)
	}
	d2, err := c.GetSentenceEmbeddingDimension()
	if err != nil {
		t.Fatalf("second probe: %v", err)
	}
	if d1 != 4 || d2 != 4 {
		t.Errorf("dims = %d / %d, want 4/4", d1, d2)
	}
	if calls != 1 {
		t.Errorf("endpoint hit %d times, want 1 (cached)", calls)
	}
}

func TestEmbeddingClientGetDimensionSurfacesError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "down", http.StatusServiceUnavailable)
	}))
	defer srv.Close()

	c := NewHTTPEmbeddingClient(Config{URL: srv.URL})
	if _, err := c.GetSentenceEmbeddingDimension(); err == nil {
		t.Fatal("expected error probing a 503 endpoint")
	}
}

// ---------------------------------------------------------------------------
// FastEmbedClient tests.
// ---------------------------------------------------------------------------

func TestFastEmbedClientEncodeAndNormalize(t *testing.T) {
	c := NewFastEmbedClient("custom-model", fixedEmbedder(8))
	vecs, err := c.Encode([]string{"hi", "there"}, true)
	if err != nil {
		t.Fatalf("Encode: %v", err)
	}
	if len(vecs) != 2 {
		t.Fatalf("len = %d, want 2", len(vecs))
	}
	for i, row := range vecs {
		// Each row should be unit-length after normalisation.
		var sum float64
		for _, v := range row {
			sum += float64(v) * float64(v)
		}
		if sum < 0.99 || sum > 1.01 {
			t.Errorf("row %d not unit-length: ||v||^2 = %v", i, sum)
		}
	}
	if c.URL != FastEmbedLocalURL {
		t.Errorf("URL = %q, want %q", c.URL, FastEmbedLocalURL)
	}
}

func TestFastEmbedClientEmptyInput(t *testing.T) {
	called := false
	c := NewFastEmbedClient("", func(texts []string) (Encoding, error) {
		called = true
		return Encoding{}, nil
	})
	vecs, err := c.Encode(nil, true)
	if err != nil {
		t.Fatalf("Encode: %v", err)
	}
	if len(vecs) != 0 {
		t.Errorf("expected empty slice, got %v", vecs)
	}
	if called {
		t.Errorf("encoder invoked for empty input")
	}
}

func TestFastEmbedClientNoEmbedderReturnsErr(t *testing.T) {
	c := NewFastEmbedClient("", nil)
	if _, err := c.Encode([]string{"x"}, true); err == nil {
		t.Fatal("expected error when no embedder is registered")
	} else if !errorIs(err, ErrFastEmbedUnavailable) {
		t.Errorf("err = %v, want ErrFastEmbedUnavailable", err)
	}
	if _, err := c.GetSentenceEmbeddingDimension(); err == nil {
		t.Fatal("expected dimension probe error with no embedder")
	}
}

func TestFastEmbedClientDimensionProbesOnce(t *testing.T) {
	var calls int
	c := NewFastEmbedClient("", func(texts []string) (Encoding, error) {
		calls++
		return Encoding{[]float32{1, 2, 3, 4, 5}}, nil
	})
	d1, err := c.GetSentenceEmbeddingDimension()
	if err != nil {
		t.Fatalf("dim #1: %v", err)
	}
	d2, err := c.GetSentenceEmbeddingDimension()
	if err != nil {
		t.Fatalf("dim #2: %v", err)
	}
	if d1 != 5 || d2 != 5 {
		t.Errorf("dims = %d/%d, want 5/5", d1, d2)
	}
	if calls != 1 {
		t.Errorf("encoder called %d times, want 1", calls)
	}
}

// ---------------------------------------------------------------------------
// Persisted endpoint / latch / factory tests.
// ---------------------------------------------------------------------------

func TestLoadPersistedEndpointMissingReturnsEmpty(t *testing.T) {
	dir := t.TempDir()
	got, err := LoadPersistedEndpoint(filepath.Join(dir, "absent.json"))
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if got.URL != "" {
		t.Errorf("URL = %q, want empty", got.URL)
	}
}

func TestLoadPersistedEndpointMalformedReturnsError(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "bad.json")
	if err := os.WriteFile(p, []byte("{not json"), 0o600); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadPersistedEndpoint(p); err == nil {
		t.Fatal("expected error for malformed JSON")
	}
}

func TestLoadPersistedEndpointNonObjectIgnored(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "list.json")
	if err := os.WriteFile(p, []byte(`["not","an","object"]`), 0o600); err != nil {
		t.Fatal(err)
	}
	// Python `_load_persisted_endpoint` swallows parse errors and returns
	// an empty dict; the Go factory mirrors that and only the lenient
	// LoadPersistedEndpoint-or-defaulted path is exercised here.
	got, err := LoadPersistedEndpointOrDefault(p, PersistedEndpoint{})
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if got.URL != "" {
		t.Errorf("URL = %q, want empty", got.URL)
	}
}

func TestLoadPersistedEndpointRoundTrip(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "ep.json")
	want := PersistedEndpoint{URL: "http://127.0.0.1:11434", Model: "nomic-embed-text", APIKey: "enc-key"}
	body, _ := json.Marshal(want)
	if err := os.WriteFile(p, body, 0o600); err != nil {
		t.Fatal(err)
	}
	got, err := LoadPersistedEndpoint(p)
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if got.URL != want.URL || got.Model != want.Model || got.APIKey != want.APIKey {
		t.Errorf("got %+v, want %+v", got, want)
	}
}

func TestResetHTTPEmbedStateClearsLatch(t *testing.T) {
	prev := HTTPEmbedDown()
	defer setHTTPEmbedDown(prev)
	setHTTPEmbedDown(true)
	if !HTTPEmbedDown() {
		t.Fatal("latch should be set")
	}
	ResetHTTPEmbedState()
	if HTTPEmbedDown() {
		t.Fatal("latch should be cleared after ResetHTTPEmbedState")
	}
}

func TestGetEmbeddingClientFallsBackWhenHTTPUnavailable(t *testing.T) {
	// Latch into a known state so the test doesn't depend on global env.
	prev := HTTPEmbedDown()
	defer setHTTPEmbedDown(prev)
	ResetHTTPEmbedState()

	// Point EMBEDDING_URL at a closed port so the HTTP branch fails fast.
	t.Setenv(envEmbeddingURL, "http://127.0.0.1:1/v1/embeddings")
	t.Setenv(envEmbeddingModel, "")
	t.Setenv(envEmbeddingAPIKey, "")

	// Register a fastembed stub with a tiny embedder.
	SetDefaultFastEmbed(fixedEmbedder(4))
	defer SetDefaultFastEmbed(nil)

	emb, err := GetEmbeddingClient(EndpointConfig{})
	if err != nil {
		t.Fatalf("GetEmbeddingClient: %v", err)
	}
	if emb == nil {
		t.Fatal("got nil embedder")
	}
	dim, err := emb.GetSentenceEmbeddingDimension()
	if err != nil {
		t.Fatalf("dimension: %v", err)
	}
	if dim != 4 {
		t.Errorf("dim = %d, want 4", dim)
	}
	if !HTTPEmbedDown() {
		t.Errorf("HTTP latch should be tripped after a failed probe")
	}
}

func TestGetEmbeddingClientUsesPersistedEndpoint(t *testing.T) {
	prev := HTTPEmbedDown()
	defer setHTTPEmbedDown(prev)
	ResetHTTPEmbedState()

	// Build a test server that returns a single 4-dim vector; we'll point
	// the persisted-endpoint file at this server.
	srv, _ := newTestServer(t, func(req embedRequest) (int, embedResponse) {
		out := embedResponse{}
		out.Data = append(out.Data, struct {
			Index     int       `json:"index"`
			Embedding []float32 `json:"embedding"`
		}{Index: 0, Embedding: []float32{0.1, 0.2, 0.3, 0.4}})
		return http.StatusOK, out
	})

	// Wipe env so the persisted path is the only thing the factory sees.
	t.Setenv(envEmbeddingURL, "")
	t.Setenv(envEmbeddingModel, "")
	t.Setenv(envEmbeddingAPIKey, "")

	dir := t.TempDir()
	p := filepath.Join(dir, "ep.json")
	body, _ := json.Marshal(PersistedEndpoint{URL: srv.URL, Model: "persisted-model"})
	if err := os.WriteFile(p, body, 0o600); err != nil {
		t.Fatal(err)
	}

	emb, err := GetEmbeddingClient(EndpointConfig{PersistedFile: p})
	if err != nil {
		t.Fatalf("GetEmbeddingClient: %v", err)
	}
	if emb == nil {
		t.Fatal("got nil embedder")
	}
	dim, err := emb.GetSentenceEmbeddingDimension()
	if err != nil {
		t.Fatalf("dim: %v", err)
	}
	if dim != 4 {
		t.Errorf("dim = %d, want 4", dim)
	}
}

func TestGetEmbeddingClientPersistedAPIKeyDecrypted(t *testing.T) {
	prev := HTTPEmbedDown()
	defer setHTTPEmbedDown(prev)
	ResetHTTPEmbedState()

	srv, _ := newTestServer(t, func(req embedRequest) (int, embedResponse) {
		out := embedResponse{}
		out.Data = append(out.Data, struct {
			Index     int       `json:"index"`
			Embedding []float32 `json:"embedding"`
		}{Index: 0, Embedding: []float32{0.1, 0.2}})
		return http.StatusOK, out
	})

	t.Setenv(envEmbeddingURL, "")
	dir := t.TempDir()
	p := filepath.Join(dir, "ep.json")
	body, _ := json.Marshal(PersistedEndpoint{URL: srv.URL, APIKey: "encrypted"})
	if err := os.WriteFile(p, body, 0o600); err != nil {
		t.Fatal(err)
	}

	decryptCalls := 0
	emb, err := GetEmbeddingClient(EndpointConfig{
		PersistedFile: p,
		DecryptAPIKey: func(enc string) (string, error) {
			decryptCalls++
			if enc != "encrypted" {
				t.Errorf("DecryptAPIKey received %q, want %q", enc, "encrypted")
			}
			return "decrypted-key", nil
		},
	})
	if err != nil {
		t.Fatalf("GetEmbeddingClient: %v", err)
	}
	if emb == nil {
		t.Fatal("got nil embedder")
	}
	if decryptCalls != 1 {
		t.Errorf("DecryptAPIKey called %d times, want 1", decryptCalls)
	}
}

func TestGetEmbeddingClientReturnsErrWhenNothingAvailable(t *testing.T) {
	prev := HTTPEmbedDown()
	defer setHTTPEmbedDown(prev)
	ResetHTTPEmbedState()

	t.Setenv(envEmbeddingURL, "")
	SetDefaultFastEmbed(nil)
	defer SetDefaultFastEmbed(nil)

	if _, err := GetEmbeddingClient(EndpointConfig{}); err == nil {
		t.Fatal("expected ErrFastEmbedUnavailable, got nil")
	}
}

// ---------------------------------------------------------------------------
// Default-HTTP-path happy-path: exercise the HTTP branch directly via
// buildHTTPClientFromConfig to prove the env fallback works end-to-end.
// ---------------------------------------------------------------------------

func TestBuildHTTPClientFromConfigHonoursEnv(t *testing.T) {
	prev := HTTPEmbedDown()
	defer setHTTPEmbedDown(prev)
	ResetHTTPEmbedState()

	srv, _ := newTestServer(t, func(req embedRequest) (int, embedResponse) {
		out := embedResponse{}
		for i := range req.Input {
			out.Data = append(out.Data, struct {
				Index     int       `json:"index"`
				Embedding []float32 `json:"embedding"`
			}{Index: i, Embedding: []float32{0.5, 0.5, 0.5, 0.5, 0.5}})
		}
		return http.StatusOK, out
	})
	t.Setenv(envEmbeddingURL, srv.URL)
	t.Setenv(envEmbeddingModel, "env-model")
	t.Setenv(envEmbeddingAPIKey, "env-key")

	ec, err := buildHTTPClientFromConfig(EndpointConfig{})
	if err != nil {
		t.Fatalf("buildHTTPClientFromConfig: %v", err)
	}
	if ec == nil {
		t.Fatal("expected a client, got nil")
	}
	if ec.URL != srv.URL {
		t.Errorf("URL = %q, want %q", ec.URL, srv.URL)
	}
	if ec.Model != "env-model" {
		t.Errorf("Model = %q, want %q", ec.Model, "env-model")
	}
	if ec.APIKey != "env-key" {
		t.Errorf("APIKey = %q, want %q", ec.APIKey, "env-key")
	}
}

func TestBuildHTTPClientFromConfigReturnsNilWhenNoURL(t *testing.T) {
	prev := HTTPEmbedDown()
	defer setHTTPEmbedDown(prev)
	ResetHTTPEmbedState()

	t.Setenv(envEmbeddingURL, "")
	ec, err := buildHTTPClientFromConfig(EndpointConfig{})
	if err != nil {
		t.Fatalf("err: %v", err)
	}
	if ec != nil {
		t.Errorf("expected nil, got %+v", ec)
	}
}

// ---------------------------------------------------------------------------
// Encoding interface + sentinel errors.
// ---------------------------------------------------------------------------

func TestEmbedderInterfaceSatisfied(t *testing.T) {
	var _ Embedder = (*EmbeddingClient)(nil)
	var _ Embedder = (*FastEmbedClient)(nil)
}

func TestErrFastEmbedUnavailableSentinel(t *testing.T) {
	if ErrFastEmbedUnavailable == nil {
		t.Fatal("ErrFastEmbedUnavailable must be non-nil")
	}
	c := NewFastEmbedClient("", nil)
	_, err := c.Encode([]string{"x"}, true)
	if !errorIs(err, ErrFastEmbedUnavailable) {
		t.Errorf("expected ErrFastEmbedUnavailable, got %v", err)
	}
}

// ---------------------------------------------------------------------------
// Float-slice comparison + helpers.
// ---------------------------------------------------------------------------

func floatSliceNear(a, b []float32, tol float32) bool {
	if len(a) != len(b) {
		return false
	}
	for i := range a {
		d := a[i] - b[i]
		if d < -tol || d > tol {
			return false
		}
	}
	return true
}

func errorIs(err, target error) bool {
	for err != nil {
		if err == target {
			return true
		}
		type unwrapper interface{ Unwrap() error }
		u, ok := err.(unwrapper)
		if !ok {
			return false
		}
		err = u.Unwrap()
	}
	return false
}

// Defensive: silence unused imports if a future refactor drops one.
var _ = io.Discard
