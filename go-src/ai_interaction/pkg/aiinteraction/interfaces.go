package aiinteraction

import (
	"context"
	"time"
)

// ---------------------------------------------------------------------------
// Injected interfaces
//
// The Python module talks to a SQL database (ModelEndpoint), an httpx
// client, ChromaDB, an in-process memory manager, a session manager, and
// a gallery row writer. The Go port models those surfaces as small
// interfaces so a caller wires them up once and the package can be
// driven from tests without a live database or HTTP transport.
// ---------------------------------------------------------------------------

// HTTPDoer is the minimal HTTP transport surface the package needs.
// net/http.Client satisfies it; tests pass a stub that records the
// request and returns a canned response.
type HTTPDoer interface {
	// Do issues a request and returns the response. The caller is
	// responsible for closing the response body if the implementation
	// returns one. The Go port does not model headers / body separately
	// — callers attach them to req before calling.
	Do(req *HTTPRequest) (*HTTPResponse, error)
}

// HTTPRequest is the minimal request shape the package needs. The
// caller is responsible for serialising body to the format the
// transport expects (the package itself never writes the bytes; it
// passes a JSON body that has already been encoded).
type HTTPRequest struct {
	Method  string
	URL     string
	Headers map[string]string
	Body    []byte
	Timeout time.Duration
}

// HTTPResponse is the minimal response shape. The transport is free to
// skip reading the full body — the package only inspects Status and
// the bytes it needs.
type HTTPResponse struct {
	Status int
	Body   []byte
}

// LLMRuntime is the surface do_pipeline needs: a single round-trip to
// a chat-completions endpoint. The Go port calls this with the
// already-resolved URL/headers/model/messages; the runtime is
// responsible for parsing the provider's response and returning the
// assistant's text.
type LLMRuntime interface {
	// Chat sends messages to endpointURL with the supplied headers and
	// returns the assistant's reply. ctx is used for cancellation.
	Chat(ctx context.Context, endpointURL, model string, headers map[string]string, messages []ChatMessage, timeout time.Duration) (string, error)
}

// ChatMessage mirrors the {"role", "content"} dict shape the Python
// source sends to llm_call_async. Role is one of "system", "user",
// "assistant"; content is the message text.
type ChatMessage struct {
	Role    string
	Content string
}

// ImageTransport is the surface do_generate_image needs: POST a JSON
// payload to the /images/generations endpoint, then optionally GET the
// returned image URL. The Go port keeps the two steps distinct so a
// caller can plug a real HTTP client without wrapping the response
// shape.
type ImageTransport interface {
	// Generate posts the supplied JSON body to imagesURL. Returns the
	// raw response bytes for the caller to parse. Status==0 means the
	// transport handled a non-2xx internally and returned an error
	// wrapped in the second return value.
	Generate(ctx context.Context, imagesURL string, headers map[string]string, body []byte) ([]byte, error)
	// Download does a GET against imageURL. Returns the raw bytes.
	Download(ctx context.Context, imageURL string) ([]byte, error)
}

// URLSafetyChecker is the surface do_generate_image needs to validate
// external image URLs before downloading. Returning ok=false stops the
// download. The Go port uses this to inject the real
// src.url_safety.check_outbound_url implementation at startup.
type URLSafetyChecker interface {
	CheckOutbound(rawURL string, blockPrivate bool) (ok bool, reason string)
}

// MemoryStore is the persistent surface do_manage_memory talks to. The
// Python source writes via the in-process memory_manager singleton;
// the Go port exposes the same surface so a caller can wire a real
// store.
type MemoryStore interface {
	// Load returns the entries for owner. owner="" returns the
	// unfiltered set (matching the Python `memory_manager.load(owner=...)`
	// call which falls back to no filter when owner is empty).
	Load(owner string) []MemoryEntry
	// LoadAll returns every entry regardless of owner.
	LoadAll() []MemoryEntry
	// Save persists the supplied entries (replacing whatever was
	// there). The Python source calls _memory_manager.save(memories)
	// after the in-memory list is mutated.
	Save(entries []MemoryEntry) error
	// AddEntry inserts a new entry and returns the persisted record
	// (with id, timestamp, etc. populated).
	AddEntry(text, source, category, owner string) (MemoryEntry, error)
	// RelevantMemories runs the manager's similarity search. Returning
	// ok=false signals the manager has no implementation and the
	// caller should fall back to a substring scan.
	RelevantMemories(query string, memories []MemoryEntry, threshold float64, maxItems int) (results []MemoryEntry, ok bool)
}

// MemoryVector is the optional Chroma-backed vector index. The Python
// source checks `hasattr(_memory_vector, 'healthy')` before calling;
// the Go port exposes a Healthy() method that mirrors that check.
type MemoryVector interface {
	Healthy() bool
	Add(id, text string) error
	Remove(id string) error
}

// RAGManager is the surface do_manage_rag talks to for indexing
// directories. The Python source delegates to
// _rag_manager.index_personal_documents.
type RAGManager interface {
	// IndexPersonalDocuments returns a count of newly-indexed files.
	// The Python source reads `result.get("indexed", 0)`.
	IndexPersonalDocuments(directory string) (map[string]int, error)
}

// PersonalDocsManager is the surface do_manage_rag talks to for
// listing and removing indexed directories. The Python source uses
// `getattr(_personal_docs_manager, 'index', [])` and similar; the Go
// port exposes the same fallbacks as methods.
type PersonalDocsManager interface {
	IndexedFiles() []any
	IndexedDirectories() []string
	RemoveDirectory(directory string) error
}

// GalleryWriter is the surface do_generate_image uses to insert a
// GalleryImage row. The Python source writes via the SQLAlchemy
// session; the Go port injects an interface so tests can capture the
// call.
type GalleryWriter interface {
	// SaveImage records a generated image. The returned id is the
	// gallery id (or "" if the writer could not persist).
	SaveImage(filename, prompt, model, size, quality, sessionID, owner string) (imageID string)
}

// SessionManager is the surface do_ui_control's switch_model action
// uses to update the active session's endpoint/model.
type SessionManager interface {
	// GetSession returns the session record (or nil if missing).
	GetSession(sessionID string) SessionRecord
	// SetSessionModel updates the session's endpoint/model/headers.
	SetSessionModel(sessionID, endpointURL, model string, headers map[string]string)
}

// SessionRecord mirrors the subset of fields switch_model touches.
type SessionRecord struct {
	ID          string
	EndpointURL string
	Model       string
	Headers     map[string]string
}

// ModelEndpointStore is the surface _resolve_model queries to find
// endpoints. The Python source reads from the SQL ModelEndpoint table
// (filtered by is_enabled and an owner_filter); the Go port exposes
// the same surface.
type ModelEndpointStore interface {
	// EnabledEndpoints returns the enabled endpoints. nameContains is
	// the case-insensitive substring filter; owner is the optional
	// owner scoping ("" means no filter).
	EnabledEndpoints(nameContains, owner string) []EndpointRecord
}

// EndpointRecord mirrors the fields _resolve_model touches on a
// ModelEndpoint row: the base URL, the cached model ids (used when
// the provider does not expose /v1/models), the API key (resolved at
// runtime by the caller), and the per-endpoint runtime config.
type EndpointRecord struct {
	Name         string
	BaseURL      string
	CachedModels []string
	// RuntimeConfig lets the caller plug in a resolver that turns the
	// stored base URL into a usable (base, api_key) pair. The Python
	// source calls resolve_endpoint_runtime(ep, owner=owner) — the Go
	// port delegates that to EndpointRuntimeResolve.
	RuntimeConfig any
}

// EndpointRuntimeResolver turns a stored endpoint into a usable
// (base, api_key) pair. The Python source calls
// resolve_endpoint_runtime(ep, owner=owner) which decrypts the API
// key, applies any per-user overrides, etc.
type EndpointRuntimeResolver func(record EndpointRecord, owner string) (base, apiKey string, err error)

// ModelResolver is the surface switch_model uses to look up a model.
// The Go port uses this same interface to drive the resolver test
// path; production callers wire it up to the live ModelEndpoint
// store.
type ModelResolver func(spec, owner string) (ResolvedModel, error)

// EventBus is the surface do_manage_memory uses to fire
// "memory_added" events. The Python source calls fire_event
// defensively; the Go port exposes a fire-and-forget interface.
type EventBus interface {
	Fire(name, owner string)
}

// PrefsStore is the surface do_ui_control's set_theme action uses to
// read user-defined custom themes. The Python source calls
// routes.prefs_routes._load(); the Go port exposes a much smaller
// surface.
type PrefsStore interface {
	// CustomThemes returns the user's custom theme map.
	CustomThemes() map[string]any
}
