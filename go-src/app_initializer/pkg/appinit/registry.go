package appinit

import "os"

// ConstructorFunc is the signature every Registry slot uses. The Config is
// passed in so constructors can derive any per-component path they need; the
// returned value is the component itself (an interface type) or nil if the
// caller accepts an absent component.
//
// Each slot is intentionally typed as `any` so the same Registry can hold
// functions returning different interface types. Initialize uses a typed
// adapter pattern internally — see initialize.go.
type ConstructorFunc func(Config) (any, error)

// Registry is the injectable construction table for Initialize. Tests swap
// individual slots to capture wiring behaviour without spinning up real
// backends; DefaultRegistry is the production wiring with stub constructors
// for everything except APIKeyManager and the directories.
type Registry struct {
	MemoryManager          ConstructorFunc
	MemoryVector           ConstructorFunc
	MemoryProviderRegistry ConstructorFunc
	SkillsManager          ConstructorFunc
	SessionManager         ConstructorFunc
	UploadHandler          ConstructorFunc
	PersonalDocsManager    ConstructorFunc
	APIKeyManager          ConstructorFunc
	PresetManager          ConstructorFunc
	ChatProcessor          ConstructorFunc
	ResearchHandler        ConstructorFunc
	ChatHandler            ConstructorFunc
	ModelDiscovery         ConstructorFunc
	BraveKeyLoader         BraveKeyLoader
}

// DefaultRegistry returns a Registry whose slots are wired to stub
// constructors. The APIKeyManager slot uses a plaintext JSON backend (good
// enough for tests; the real prod system uses Fernet-encrypted keys, but
// that pulls in a crypto dep we don't need here).
//
// Callers can override individual slots before passing the Registry into
// Initialize.
func DefaultRegistry() Registry {
	return Registry{
		MemoryManager:          stubConstructor[MemoryManager]("memory_manager"),
		MemoryVector:           stubConstructor[MemoryVector]("memory_vector"),
		MemoryProviderRegistry: stubConstructor[MemoryProviderRegistry]("memory_provider_registry"),
		SkillsManager:          stubConstructor[SkillsManager]("skills_manager"),
		SessionManager:         stubConstructor[SessionManager]("session_manager"),
		UploadHandler:          stubConstructor[UploadHandler]("upload_handler"),
		PersonalDocsManager:    stubConstructor[PersonalDocsManager]("personal_docs_manager"),
		APIKeyManager:          defaultAPIKeyConstructor,
		PresetManager:          stubConstructor[PresetManager]("preset_manager"),
		ChatProcessor:          stubConstructor[ChatProcessor]("chat_processor"),
		ResearchHandler:        stubConstructor[ResearchHandler]("research_handler"),
		ChatHandler:            stubConstructor[ChatHandler]("chat_handler"),
		ModelDiscovery:         stubConstructor[ModelDiscovery]("model_discovery"),
		BraveKeyLoader:         NoopBraveKeyLoader{},
	}
}

// stubConstructor returns a ConstructorFunc that always returns nil. The name
// is kept only so logs can identify which slot failed if a downstream caller
// NPE-checks. This mirrors the Python orchestrator's "construct everything,
// some may be None" pattern.
func stubConstructor[T any](name string) ConstructorFunc {
	return func(_ Config) (any, error) {
		_ = name
		return nil, nil
	}
}

// defaultAPIKeyConstructor wires a plaintext JSON backend. It does NOT
// implement Fernet — the test backend simply stores keys in api_keys.json as
// plaintext. Real prod uses Fernet (Python src/api_key_manager.py); for the
// Go port we keep it stdlib-only.
func defaultAPIKeyConstructor(cfg Config) (any, error) {
	return &jsonAPIKeyManager{path: cfg.APIKeysFile}, nil
}

// jsonAPIKeyManager is a tiny stdlib-only APIKeyManager. It is intentionally
// NOT encryption-aware: prod systems use Fernet, but that drags in a crypto
// dep we want to avoid for the port. See README for the trade-off.
type jsonAPIKeyManager struct {
	path string
}

func (j *jsonAPIKeyManager) Load() map[string]string {
	f, err := os.Open(j.path)
	if err != nil {
		return map[string]string{}
	}
	defer f.Close()
	return decodeKeyFile(f)
}

func (j *jsonAPIKeyManager) Save(provider, key string) error {
	keys := j.Load()
	keys[provider] = key
	return writeKeyFile(j.path, keys)
}

// NoopBraveKeyLoader is the default BraveKeyLoader. UpdateSearchConfig is a
// no-op so tests can run without a search subsystem.
type NoopBraveKeyLoader struct{}

// UpdateSearchConfig satisfies BraveKeyLoader and intentionally does nothing.
func (NoopBraveKeyLoader) UpdateSearchConfig(_ string) error { return nil }
