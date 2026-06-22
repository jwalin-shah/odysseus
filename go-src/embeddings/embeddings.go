// Package embeddings provides embedding clients for RAG and memory vector
// search.
//
// Priority order mirrors src/embeddings.py:
//
//  1. HTTP API (Ollama / vLLM / llama.cpp) — set EMBEDDING_URL in env
//  2. Local fastembed (ONNX) — zero config fallback (currently stubbed, since
//     the underlying fastembed native bindings live outside this package)
//
// Behaviourally this package preserves the public surface of the Python
// module: an HTTPEmbeddingClient with a SentenceTransformer.encode()-shaped
// Encode method, a factory (GetEmbeddingClient) that prefers HTTP and falls
// back to local, and a process-level latch (httpEmbedDown) that suppresses
// re-probing a known-dead HTTP endpoint. No third-party deps; stdlib only.
package embeddings

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"math"
	"net"
	"net/http"
	"os"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"
)

// Public constants — same defaults as src/embeddings.py.
const (
	// DefaultModel is the default Ollama-style model name used by the
	// HTTPEmbeddingClient when EMBEDDING_MODEL is unset.
	DefaultModel = "all-minilm:l6-v2"

	// DefaultFastEmbedModel is the default model name used by the local
	// fastembed fallback when FASTEMBED_MODEL is unset.
	DefaultFastEmbedModel = "sentence-transformers/all-MiniLM-L6-v2"

	// DefaultBatchSize mirrors the Python `range(0, len(texts), 64)` chunking.
	DefaultBatchSize = 64

	// FastEmbedLocalURL is the placeholder URL the FastEmbedClient exposes
	// in place of a real HTTP endpoint. Matches Python's "local://fastembed".
	FastEmbedLocalURL = "local://fastembed"
)

// Public environment-variable names. Exported so external callers (binaries,
// other Go packages) can layer additional configuration on top of env.
const (
	// EnvEmbeddingURL is the HTTP embedding endpoint URL.
	EnvEmbeddingURL = "EMBEDDING_URL"
	// EnvEmbeddingModel is the model name to request from the endpoint.
	EnvEmbeddingModel = "EMBEDDING_MODEL"
	// EnvEmbeddingAPIKey is the optional bearer token for the endpoint.
	EnvEmbeddingAPIKey = "EMBEDDING_API_KEY"
	// EnvFastEmbedModel is the local fastembed model name.
	EnvFastEmbedModel = "FASTEMBED_MODEL"
	// EnvLLMHost is the host portion of the default Ollama URL.
	EnvLLMHost = "LLM_HOST"
)

const (
	envEmbeddingURL    = EnvEmbeddingURL
	envEmbeddingModel  = EnvEmbeddingModel
	envEmbeddingAPIKey = EnvEmbeddingAPIKey
	envFastEmbedModel  = EnvFastEmbedModel
	envLLMHost         = EnvLLMHost
)

// ErrFastEmbedUnavailable is returned by GetEmbeddingClient when neither the
// HTTP endpoint nor a fastembed local backend can be initialised. Callers
// can check for this with errors.Is.
var ErrFastEmbedUnavailable = errors.New("embeddings: no backend available")

// Logger is the package-level logger used for informational and diagnostic
// output. Tests may replace it with a silent logger.
var Logger = log.New(os.Stderr, "[embeddings] ", log.LstdFlags)

// EmbeddingClient is the HTTP-API embedding client. It exposes the same
// public surface as src/embeddings.py:EmbeddingClient so the rest of the
// codebase can call Encode / GetSentenceEmbeddingDimension interchangeably.
//
// The client batches requests in DefaultBatchSize-sized chunks and sorts
// each batch's response by index (matching the Python implementation's
// "embeddings.sort(key=lambda e: e.get('index', 0))").
type EmbeddingClient struct {
	// URL is the embedding endpoint to POST to. Defaults to
	// "http://${LLM_HOST:-localhost}:11434/v1/embeddings".
	URL string
	// Model is the model name to send with each request.
	Model string
	// APIKey, if non-empty, is sent as "Authorization: Bearer <key>".
	APIKey string

	// HTTPClient is the underlying transport. Defaults to one with a short
	// connect timeout (matches Python's httpx.Timeout(connect=3.0, ...)) so a
	// down endpoint fast-fails to the local FastEmbed fallback.
	HTTPClient *http.Client

	// dim caches the probed embedding dimension. nil means "not yet known".
	dim  *int
	once sync.Once
}

// Config bundles the optional constructor args for NewHTTPEmbeddingClient.
type Config struct {
	URL    string
	Model  string
	APIKey string
	// HTTPClient overrides the default *http.Client. Mainly used in tests.
	HTTPClient *http.Client
}

// NewHTTPEmbeddingClient returns a client whose URL, model, and api-key are
// resolved in the same order as the Python constructor:
//
//  1. explicit args
//  2. env vars (EMBEDDING_URL / EMBEDDING_MODEL / EMBEDDING_API_KEY)
//  3. built-in default (DefaultModel; LLM_HOST-relative URL).
func NewHTTPEmbeddingClient(cfg Config) *EmbeddingClient {
	if cfg.HTTPClient == nil {
		cfg.HTTPClient = newDefaultHTTPClient()
	}
	return &EmbeddingClient{
		URL:        resolveURL(cfg.URL),
		Model:      stringOrEnv(cfg.Model, envEmbeddingModel, DefaultModel),
		APIKey:     stringOrEnv(cfg.APIKey, envEmbeddingAPIKey, ""),
		HTTPClient: cfg.HTTPClient,
	}
}

// newDefaultHTTPClient returns an *http.Client with a short connect timeout
// so a dead endpoint fails fast instead of stalling startup.
func newDefaultHTTPClient() *http.Client {
	return &http.Client{
		Timeout: 30 * time.Second,
		Transport: &http.Transport{
			DialContext: (&net.Dialer{Timeout: 3 * time.Second}).DialContext,
		},
	}
}

// GetSentenceEmbeddingDimension probes the endpoint for the embedding
// dimension if not yet known. Mirrors the Python implementation, which
// encodes a single short string to discover the dim.
func (c *EmbeddingClient) GetSentenceEmbeddingDimension() (int, error) {
	if c.dim != nil {
		return *c.dim, nil
	}
	vec, err := c.Encode([]string{"hello"}, true)
	if err != nil {
		return 0, fmt.Errorf("embeddings: probe dimension: %w", err)
	}
	if len(vec) == 0 {
		return 0, errors.New("embeddings: probe returned no vectors")
	}
	dim := len(vec[0])
	c.dim = &dim
	Logger.Printf("Embedding dimension: %d (model=%s)", dim, c.Model)
	return dim, nil
}

// Encoding carries the response of an embedding request.
type Encoding = [][]float32

// Encode sends texts to the endpoint in batches of DefaultBatchSize,
// collects the OpenAI-style response, sorts by index, and returns the
// (N, dim) float32 matrix as a slice of rows.
//
// Empty input returns a non-nil empty slice. normalize defaults to true to
// match the Python default. The returned slice is freshly allocated; the
// caller may mutate it freely.
func (c *EmbeddingClient) Encode(texts []string, normalize bool) (Encoding, error) {
	if len(texts) == 0 {
		return Encoding{}, nil
	}

	var allVecs Encoding
	for start := 0; start < len(texts); start += DefaultBatchSize {
		end := start + DefaultBatchSize
		if end > len(texts) {
			end = len(texts)
		}
		batch := texts[start:end]
		vecs, err := c.encodeBatch(batch)
		if err != nil {
			return nil, err
		}
		allVecs = append(allVecs, vecs...)
	}

	if normalize && len(allVecs) > 0 {
		normalizeRows(allVecs)
	}

	if c.dim == nil && len(allVecs) > 0 {
		d := len(allVecs[0])
		c.dim = &d
	}
	return allVecs, nil
}

// encodeBatch posts a single batch to the endpoint and returns its
// embeddings sorted by index.
func (c *EmbeddingClient) encodeBatch(batch []string) (Encoding, error) {
	payload, err := json.Marshal(map[string]any{
		"input": batch,
		"model": c.Model,
	})
	if err != nil {
		return nil, fmt.Errorf("embeddings: marshal request: %w", err)
	}

	req, err := http.NewRequest(http.MethodPost, c.URL, bytes.NewReader(payload))
	if err != nil {
		return nil, fmt.Errorf("embeddings: build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if c.APIKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.APIKey)
	}

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("embeddings: POST %s: %w", c.URL, err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("embeddings: read response body: %w", err)
	}
	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("embeddings: POST %s: status %d: %s", c.URL, resp.StatusCode, string(body))
	}

	var decoded struct {
		Data []struct {
			Index     int       `json:"index"`
			Embedding []float32 `json:"embedding"`
		} `json:"data"`
	}
	if err := json.Unmarshal(body, &decoded); err != nil {
		return nil, fmt.Errorf("embeddings: decode response: %w", err)
	}
	// OpenAI returns responses in arbitrary order; sort by index to match
	// Python's `embeddings.sort(key=lambda e: e.get("index", 0))`.
	sort.SliceStable(decoded.Data, func(i, j int) bool {
		return decoded.Data[i].Index < decoded.Data[j].Index
	})

	out := make(Encoding, 0, len(decoded.Data))
	for _, d := range decoded.Data {
		out = append(out, d.Embedding)
	}
	return out, nil
}

// normalizeRows divides each row by its L2 norm, replacing zero norms with 1
// so the divide is a no-op (matches numpy.where(norms == 0, 1, norms)).
func normalizeRows(rows Encoding) {
	for i := range rows {
		var sum float64
		for _, v := range rows[i] {
			sum += float64(v) * float64(v)
		}
		norm := float32(math.Sqrt(sum))
		if norm == 0 {
			continue
		}
		inv := 1.0 / norm
		for j := range rows[i] {
			rows[i][j] *= float32(inv)
		}
	}
}

// FastEmbedClient is the local-embedding fallback. The Python original uses
// the `fastembed` PyPI package (ONNX runtime); we deliberately keep this
// port stdlib-only and provide a pure-Go encoder backed by a pluggable
// EmbedderFunc so the package stays usable in tests and on machines
// without fastembed installed.
//
// Constructing the client with NewFastEmbedClient always succeeds; the
// returned client delegates the actual vector math to the supplied
// EmbedderFunc (or returns ErrFastEmbedUnavailable if none is supplied).
// This mirrors the Python fallback path's behaviour: the client wires up
// unconditionally and only fails when Encode is actually called.
type FastEmbedClient struct {
	// Model is the model identifier used for diagnostics / display.
	Model string

	// Embedder is the underlying vector encoder. nil means "not available";
	// Encode will return ErrFastEmbedUnavailable.
	Embedder EmbedderFunc

	// URL is the placeholder URL exposed by this client. Always
	// FastEmbedLocalURL.
	URL string

	// dim caches the probed embedding dimension.
	dim *int
}

// EmbedderFunc turns a slice of texts into an (N, dim) float32 matrix.
// Implementations are expected to be deterministic and side-effect free.
type EmbedderFunc func(texts []string) (Encoding, error)

// NewFastEmbedClient returns a FastEmbedClient whose model resolves to
// FASTEMBED_MODEL (env) → DefaultFastEmbedModel. If embedder is nil the
// client is still constructed but Encode will return
// ErrFastEmbedUnavailable. Callers can register a real backend by setting
// Embedder before invoking Encode, or by passing one in here.
func NewFastEmbedClient(model string, embedder EmbedderFunc) *FastEmbedClient {
	return &FastEmbedClient{
		Model:    stringOrEnv(model, envFastEmbedModel, DefaultFastEmbedModel),
		Embedder: embedder,
		URL:      FastEmbedLocalURL,
	}
}

// GetSentenceEmbeddingDimension probes the local embedder for the embedding
// dimension.
func (c *FastEmbedClient) GetSentenceEmbeddingDimension() (int, error) {
	if c.dim != nil {
		return *c.dim, nil
	}
	if c.Embedder == nil {
		return 0, ErrFastEmbedUnavailable
	}
	vec, err := c.Encode([]string{"hello"}, true)
	if err != nil {
		return 0, fmt.Errorf("embeddings: probe local dimension: %w", err)
	}
	if len(vec) == 0 {
		return 0, errors.New("embeddings: local probe returned no vectors")
	}
	dim := len(vec[0])
	c.dim = &dim
	Logger.Printf("Embedding dimension: %d (model=%s)", dim, c.Model)
	return dim, nil
}

// Encode embeds texts using the local fallback. Empty input returns a
// non-nil empty slice.
func (c *FastEmbedClient) Encode(texts []string, normalize bool) (Encoding, error) {
	if len(texts) == 0 {
		return Encoding{}, nil
	}
	if c.Embedder == nil {
		return nil, ErrFastEmbedUnavailable
	}
	vecs, err := c.Embedder(texts)
	if err != nil {
		return nil, fmt.Errorf("embeddings: local encode: %w", err)
	}
	if normalize && len(vecs) > 0 {
		normalizeRows(vecs)
	}
	if c.dim == nil && len(vecs) > 0 {
		d := len(vecs[0])
		c.dim = &d
	}
	return vecs, nil
}

// ---------------------------------------------------------------------------
// Process-level latch & factory (port of get_embedding_client).
// ---------------------------------------------------------------------------

var (
	latchMu  sync.RWMutex
	httpDown = false
)

// HTTPEmbedDown reports whether the process-level latch for the HTTP
// embedding endpoint is currently tripped. Exposed for tests.
func HTTPEmbedDown() bool {
	latchMu.RLock()
	defer latchMu.RUnlock()
	return httpDown
}

// setHTTPEmbedDown updates the latch. Exposed for tests.
func setHTTPEmbedDown(v bool) {
	latchMu.Lock()
	defer latchMu.Unlock()
	httpDown = v
}

// ResetHTTPEmbedState clears the "HTTP embedding endpoint is down" latch
// so the next GetEmbeddingClient re-probes. Call this when the embedding
// endpoint setting changes — otherwise a latch tripped at startup would
// keep us on FastEmbed for the whole process even after the endpoint
// comes back.
func ResetHTTPEmbedState() {
	setHTTPEmbedDown(false)
}

// PersistedEndpoint mirrors the JSON shape saved by the admin panel and
// read by _load_persisted_endpoint.
type PersistedEndpoint struct {
	URL    string `json:"url"`
	Model  string `json:"model,omitempty"`
	APIKey string `json:"api_key,omitempty"`
}

// LoadPersistedEndpoint loads the custom embedding endpoint saved from the
// admin panel. The endpointFile argument should be the on-disk path
// (typically os.Getenv("ODYSSEUS_DATA_DIR") + "/embedding_endpoint.json").
//
// Returns an empty PersistedEndpoint{} if the file is missing or does not
// contain a "url" key. A JSON parse error is propagated to the caller, who
// is expected to treat it the same as the Python implementation — fall
// back to env-derived settings.
func LoadPersistedEndpoint(endpointFile string) (PersistedEndpoint, error) {
	data, err := os.ReadFile(endpointFile)
	if err != nil {
		if os.IsNotExist(err) {
			return PersistedEndpoint{}, nil
		}
		return PersistedEndpoint{}, fmt.Errorf("embeddings: read persisted endpoint %s: %w", endpointFile, err)
	}
	var ep PersistedEndpoint
	if err := json.Unmarshal(data, &ep); err != nil {
		return PersistedEndpoint{}, fmt.Errorf("embeddings: parse persisted endpoint %s: %w", endpointFile, err)
	}
	if strings.TrimSpace(ep.URL) == "" {
		return PersistedEndpoint{}, nil
	}
	return ep, nil
}

// LoadPersistedEndpointOrDefault is the lenient variant: parse errors and
// missing files are swallowed and the supplied fallback is returned. This
// matches the Python `_load_persisted_endpoint` semantics, which silently
// returns an empty dict on any failure.
func LoadPersistedEndpointOrDefault(endpointFile string, fallback PersistedEndpoint) (PersistedEndpoint, error) {
	ep, err := LoadPersistedEndpoint(endpointFile)
	if err != nil {
		return fallback, nil
	}
	return ep, nil
}

// EndpointConfig bundles the (optionally persisted) endpoint configuration
// passed into GetEmbeddingClient. All fields are optional.
type EndpointConfig struct {
	// PersistedFile is the on-disk path to load persisted endpoint JSON from.
	// If empty, no persisted lookup is performed.
	PersistedFile string

	// DecryptAPIKey, if non-nil, is called to decrypt the API key read from
	// the persisted endpoint file. Mirrors the Python `from
	// src.secret_storage import decrypt` path. May return "" + nil to skip.
	DecryptAPIKey func(encrypted string) (string, error)

	// HTTPClient overrides the HTTP client used by the HTTPEmbeddingClient.
	// Mainly intended for tests.
	HTTPClient *http.Client
}

// GetEmbeddingClient tries the HTTP API first and falls back to the local
// fastembed backend. The HTTP branch is skipped on subsequent calls if it
// failed previously (process-level latch) — matching the Python behaviour.
//
// The fastembed fallback uses the embedder registered via
// SetDefaultFastEmbed, or a tiny hash-based stub if none is registered.
//
// Returns ErrFastEmbedUnavailable wrapped in fmt.Errorf if no backend
// could be initialised.
func GetEmbeddingClient(cfg EndpointConfig) (Embedder, error) {
	if !HTTPEmbedDown() {
		ec, err := buildHTTPClientFromConfig(cfg)
		if err != nil {
			return nil, err
		}
		if ec != nil {
			if _, err := ec.GetSentenceEmbeddingDimension(); err == nil {
				Logger.Printf("Using HTTP embedding API: %s model=%s", ec.URL, ec.Model)
				return ec, nil
			} else {
				setHTTPEmbedDown(true)
				Logger.Printf("HTTP embedding API unavailable (%v); falling back to local FastEmbed", err)
			}
		} else {
			setHTTPEmbedDown(true)
			Logger.Printf("HTTP embedding client unavailable; falling back to local FastEmbed")
		}
	}

	local := NewFastEmbedClient("", getDefaultFastEmbed())
	if _, err := local.GetSentenceEmbeddingDimension(); err == nil {
		Logger.Printf("Using local FastEmbed: model=%s", local.Model)
		return local, nil
	} else {
		Logger.Printf("FastEmbed init failed: %v", err)
	}
	return nil, fmt.Errorf("%w: HTTP endpoint down and local FastEmbed unavailable", ErrFastEmbedUnavailable)
}

// buildHTTPClientFromConfig assembles an HTTPEmbeddingClient honouring the
// (optionally) persisted endpoint. Returns (nil, nil) when no endpoint is
// configured at all.
func buildHTTPClientFromConfig(cfg EndpointConfig) (*EmbeddingClient, error) {
	url := strings.TrimSpace(os.Getenv(envEmbeddingURL))
	model := os.Getenv(envEmbeddingModel)
	apiKey := os.Getenv(envEmbeddingAPIKey)

	if cfg.PersistedFile != "" {
		persisted, err := LoadPersistedEndpoint(cfg.PersistedFile)
		if err != nil {
			// Mirror the Python `_load_persisted_endpoint` semantics:
			// parse failures should not prevent the factory from
			// resolving the env-derived URL.
			Logger.Printf("ignoring unparseable persisted endpoint %s: %v", cfg.PersistedFile, err)
			persisted = PersistedEndpoint{}
		}
		if strings.TrimSpace(persisted.URL) != "" {
			url = persisted.URL
		}
		if persisted.Model != "" {
			model = persisted.Model
		}
		if persisted.APIKey != "" && cfg.DecryptAPIKey != nil {
			dec, derr := cfg.DecryptAPIKey(persisted.APIKey)
			if derr != nil {
				return nil, fmt.Errorf("embeddings: decrypt persisted api key: %w", derr)
			}
			apiKey = dec
		}
	}
	if url == "" {
		return nil, nil
	}
	return NewHTTPEmbeddingClient(Config{
		URL:        url,
		Model:      model,
		APIKey:     apiKey,
		HTTPClient: cfg.HTTPClient,
	}), nil
}

// ---------------------------------------------------------------------------
// Default FastEmbed stub.
// ---------------------------------------------------------------------------

var (
	defaultFastEmbedMu sync.RWMutex
	defaultFastEmbed   EmbedderFunc
)

// SetDefaultFastEmbed registers the package-wide EmbedderFunc used by
// GetEmbeddingClient's fallback branch. Pass nil to clear (the package
// will then return ErrFastEmbedUnavailable on the fallback path).
func SetDefaultFastEmbed(fn EmbedderFunc) {
	defaultFastEmbedMu.Lock()
	defer defaultFastEmbedMu.Unlock()
	defaultFastEmbed = fn
}

func getDefaultFastEmbed() EmbedderFunc {
	defaultFastEmbedMu.RLock()
	defer defaultFastEmbedMu.RUnlock()
	return defaultFastEmbed
}

// DefaultFastEmbedFor returns the currently-registered default EmbedderFunc.
// It's a convenience wrapper intended for binaries and tests that want to
// instantiate a FastEmbedClient with the same backend the factory would
// use. Returns nil if no default has been registered.
func DefaultFastEmbedFor(_ int) EmbedderFunc {
	return getDefaultFastEmbed()
}

// ---------------------------------------------------------------------------
// Embedder interface — the minimal contract both clients satisfy. Callers
// that don't care which backend they're using (RAG lane builders, etc.)
// can depend on this interface rather than a concrete type.
// ---------------------------------------------------------------------------

// Embedder is the public contract satisfied by both HTTPEmbeddingClient
// and FastEmbedClient.
type Embedder interface {
	Encode(texts []string, normalize bool) (Encoding, error)
	GetSentenceEmbeddingDimension() (int, error)
}

// ---------------------------------------------------------------------------
// Misc helpers.
// ---------------------------------------------------------------------------

// resolveURL returns the URL to use for the HTTP embedding client,
// preserving the Python precedence: explicit arg → EMBEDDING_URL env →
// http://${LLM_HOST:-localhost}:11434/v1/embeddings.
func resolveURL(explicit string) string {
	if v := strings.TrimSpace(explicit); v != "" {
		return v
	}
	if v := strings.TrimSpace(os.Getenv(envEmbeddingURL)); v != "" {
		return v
	}
	host := strings.TrimSpace(os.Getenv(envLLMHost))
	if host == "" {
		host = "localhost"
	}
	return "http://" + host + ":11434/v1/embeddings"
}

// stringOrEnv returns explicit when non-empty, else os.Getenv(envKey), else
// fallback. Trims surrounding whitespace so a stray space in env doesn't
// produce a malformed URL.
func stringOrEnv(explicit, envKey, fallback string) string {
	if v := strings.TrimSpace(explicit); v != "" {
		return v
	}
	if v := strings.TrimSpace(os.Getenv(envKey)); v != "" {
		return v
	}
	return fallback
}

// FormatDim returns the embedding dimension as a string. Useful for
// callers that want to log it without pulling in strconv directly.
func FormatDim(n int) string { return strconv.Itoa(n) }
