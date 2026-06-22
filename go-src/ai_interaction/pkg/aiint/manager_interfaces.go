package aiint

import (
	"context"
	"os"
	"path/filepath"
)

// MemoryEntry mirrors the dict shape stored by the Python MemoryManager:
// id, text, category, owner, plus a timestamp-like value the Python code
// touches (`m["timestamp"] = int(time.time())` on edit). We keep only the
// fields this package consumes.
type MemoryEntry struct {
	ID       string `json:"id"`
	Text     string `json:"text"`
	Category string `json:"category"`
	Owner    string `json:"owner,omitempty"`
}

// RAGDoc is a minimal indexed-document record. The Python module exposes a
// richer object on _personal_docs_manager.index; we only model the names
// referenced by list output.
type RAGDoc struct {
	Path  string `json:"path"`
	Name  string `json:"name,omitempty"`
	Size  int64  `json:"size,omitempty"`
	Owner string `json:"owner,omitempty"`
}

// Result is the envelope every handler returns. The Python module returns
// ad-hoc dicts with optional "error"/"results"/"action" keys; the Go port
// normalizes those into a typed envelope plus a free-form Details map so
// callers can preserve the original shape.
type Result struct {
	OK      bool           `json:"ok"`
	Details map[string]any `json:"details,omitempty"`
	Results string         `json:"results,omitempty"`
	Error   string         `json:"error,omitempty"`
	Action  string         `json:"action,omitempty"`
}

// ----------------------------------------------------------------------------
// Manager interfaces.
//
// The Python module's globals (_session_manager, _memory_manager, _memory_vector,
// _rag_manager, _personal_docs_manager) are replaced here by explicit Manager
// struct + interface fields. Tests construct a Manager with stub interfaces so
// no I/O happens outside t.TempDir().
// ----------------------------------------------------------------------------

// SessionManager is the seam for the small slice of session ops the
// do_manage_memory / ui_control handlers touch.
type SessionManager interface{}

// MemoryManager owns the memory store. load + load_all return the full set;
// add_entry returns the persisted entry (with id). get_relevant_memories is
// optional — fall back to text search if it isn't present (mirrors Python's
// hasattr fallback).
type MemoryManager interface {
	Load(owner string) []MemoryEntry
	LoadAll() []MemoryEntry
	AddEntry(text, source, category, owner string) (MemoryEntry, error)
	Save(entries []MemoryEntry) error
}

// MemoryVector is the optional vector index sidecar. Methods return an error
// so the manager can silently drop vector updates when not configured.
type MemoryVector interface {
	Add(id, text string) error
	Remove(id string) error
	Healthy() bool
}

// RagManager owns RAG-indexing operations. IndexPersonalDocuments returns the
// number of files indexed.
type RagManager interface {
	IndexPersonalDocuments(directory string) (RAGIndexResult, error)
}

// RAGIndexResult is the partial payload returned by IndexPersonalDocuments.
// Mirrors the `{"indexed": N}` dict shape in the Python module.
type RAGIndexResult struct {
	Indexed int `json:"indexed"`
}

// PersonalDocsManager owns per-user document directory bookkeeping.
type PersonalDocsManager interface {
	IndexedDirectories() []string
	Index() []RAGDoc
	RemoveDirectory(directory string) error
}

// ModelResolver resolves a model spec to the tuple (endpoint_url, model_id,
// headers). The Python `_resolve_model` is HTTP-heavy; this interface keeps
// only the seam.
type ModelResolver interface {
	Resolve(ctx context.Context, spec, owner string) (ResolvedModel, error)
}

// ResolvedModel is the (url, model_id, headers) tuple.
type ResolvedModel struct {
	URL     string
	ModelID string
	Headers map[string]string
}

// LLMRunner executes a single chat-completion request. The pipeline calls this
// once per resolved step. Production wiring hits llm_call_async; tests use a
// counting stub.
type LLMRunner interface {
	Complete(ctx context.Context, url, modelID string, headers map[string]string, messages []ChatMessage) (string, error)
}

// ChatMessage mirrors the {"role": "...", "content": "..."} dict used by the
// pipeline message list.
type ChatMessage struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

// ImageRunner executes an image generation request. HTTP-heavy in production.
// Set to a stub that returns ErrUnsupported when the calling tool needs to
// short-circuit.
type ImageRunner interface {
	Generate(ctx context.Context, prompt, model, size, quality, owner string) (ImageResult, error)
}

// ImageResult mirrors the Python module's image-result dict.
type ImageResult struct {
	URL     string `json:"image_url"`
	ID      string `json:"image_id"`
	Prompt  string `json:"image_prompt"`
	Model   string `json:"image_model"`
	Size    string `json:"image_size"`
	Quality string `json:"image_quality"`
	Summary string `json:"results"`
}

// Manager bundles all the runtime dependencies the handlers need. The Python
// module uses module-level globals; here we use a struct so tests can build
// one with stubs.
type Manager struct {
	Session      SessionManager
	Memory       MemoryManager
	MemoryVector MemoryVector
	RAG          RagManager
	PersonalDocs PersonalDocsManager
	Resolver     ModelResolver
	LLM          LLMRunner
	Image        ImageRunner
	// Now is injectable so tests can pin timestamps. Defaults to time.Now.
	Now func() int64
	// HomeDir overrides os.UserHomeDir for `~` expansion in manage_rag.
	// Defaults to os.UserHomeDir.
	HomeDir func() (string, error)
}

// resolveHome returns m.HomeDir or os.UserHomeDir. Centralized so tests can
// swap to t.TempDir().
func (m *Manager) resolveHome() (string, error) {
	if m != nil && m.HomeDir != nil {
		return m.HomeDir()
	}
	return os.UserHomeDir()
}

// ExpandHome expands a leading `~` to the resolved home dir.
func ExpandHome(home, path string) string {
	if len(path) == 0 {
		return path
	}
	if path[0] != '~' {
		return path
	}
	if home == "" {
		return path
	}
	if len(path) == 1 {
		return home
	}
	if path[1] == '/' || path[1] == filepath.Separator {
		return filepath.Join(home, path[2:])
	}
	return filepath.Join(home, path[1:])
}
