// Package appinit — manager interfaces.
//
// Each interface captures only the methods the rest of the app actually calls
// on the corresponding component (per app_initializer.py). This is the
// dependency boundary that lets Initialize run with no-op stubs: a stub
// satisfies the interface by returning the zero value and the orchestrator
// never has to know whether the real FastAPI/Chroma/MCP backend is wired.
package appinit

// MemoryManager owns persistent key/value memory entries.
type MemoryManager interface {
	Load() []map[string]any
	Save(entries []map[string]any) error
}

// SkillsManager owns the on-disk skills catalogue.
type SkillsManager interface {
	List() []string
}

// SessionManager owns the chat session ledger (sessions.json).
type SessionManager interface {
	AddMessage(sessionID, role, content string) error
	History(sessionID string) []map[string]any
}

// UploadHandler accepts uploaded files into the upload directory.
type UploadHandler interface {
	Accept(filename string, data []byte) (string, error)
}

// PersonalDocsManager indexes the user's personal documents directory.
type PersonalDocsManager interface {
	Index() []map[string]any
	Rebuild() error
}

// APIKeyManager stores provider API keys (encrypted at rest by the real impl;
// the default in this port uses a plaintext JSON backend for testability).
type APIKeyManager interface {
	Load() map[string]string
	Save(provider, key string) error
}

// PresetManager owns the chat preset catalogue.
type PresetManager interface {
	List() []map[string]any
}

// ChatProcessor turns a user message + memory + skills into a chat reply.
type ChatProcessor interface {
	Process(message string, sessionID string) (string, error)
}

// ResearchHandler drives multi-step research tasks.
type ResearchHandler interface {
	Start(query string) (string, error)
	Status(taskID string) (string, error)
}

// ChatHandler is the high-level chat dispatcher.
type ChatHandler interface {
	Handle(sessionID, message string) (string, error)
}

// ModelDiscovery enumerates available chat models.
type ModelDiscovery interface {
	Discover() ([]string, error)
}

// MemoryVector is the optional Chroma-backed vector index over memories.
type MemoryVector interface {
	Count() int
	Healthy() bool
	Rebuild(entries []map[string]any) error
}

// MemoryProviderRegistry routes memory reads/writes across providers.
type MemoryProviderRegistry interface {
	Register(name string, provider MemoryProvider)
	Get(name string) (MemoryProvider, bool)
}

// MemoryProvider is a single backend (native JSON, vector, ...).
type MemoryProvider interface {
	Name() string
	Load() []map[string]any
}

// BraveKeyLoader is the tiny surface the orchestrator needs to push a loaded
// "brave" key into the search subsystem. DefaultRegistry wires a no-op.
type BraveKeyLoader interface {
	UpdateSearchConfig(apiKey string) error
}
