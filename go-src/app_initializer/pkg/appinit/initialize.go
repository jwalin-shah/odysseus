// Package appinit — the orchestrator.
//
// CreateDirectories ensures the four required directories exist (idempotent,
// uses os.MkdirAll).
//
// Initialize wires every component from a Registry and returns an AppContext
// that mirrors the dict returned by the Python initialize_managers function.
// The Registry's APIKeyManager slot is consulted to load saved keys; if a key
// named "brave" exists, the configured BraveKeyLoader is called.
package appinit

import (
	"fmt"
	"os"
)

// AppContext holds every component the Python orchestrator returns. The
// fields are interfaces so a stub registry (or a test double) can stand in
// for the real FastAPI/Chroma/MCP-backed implementations.
type AppContext struct {
	MemoryManager          MemoryManager
	MemoryVector           MemoryVector
	MemoryProviderRegistry MemoryProviderRegistry
	SkillsManager          SkillsManager
	SessionManager         SessionManager
	UploadHandler          UploadHandler
	PersonalDocsManager    PersonalDocsManager
	APIKeyManager          APIKeyManager
	PresetManager          PresetManager
	ChatProcessor          ChatProcessor
	ResearchHandler        ResearchHandler
	ChatHandler            ChatHandler
	ModelDiscovery         ModelDiscovery

	// CurrentPresets is the catalogue view exposed by the PresetManager. The
	// Python return value keys this as "current_presets".
	CurrentPresets []map[string]any

	// PersonalIndex is the indexed personal-docs view (PERSONAL_INDEX in the
	// Python module). Held as a plain slice so it survives even when
	// PersonalDocsManager is a nil stub.
	PersonalIndex []map[string]any
}

// CreateDirectories creates DataDir, PersonalDir, RunbookDir, and UploadDir
// (idempotent — re-running with existing dirs is a no-op). It mirrors the
// Python create_directories helper byte-for-byte in spirit.
func CreateDirectories(cfg Config) error {
	for _, dir := range cfg.RequiredDirectories() {
		if err := os.MkdirAll(dir, 0o755); err != nil {
			return fmt.Errorf("appinit: create %s: %w", dir, err)
		}
	}
	return nil
}

// Initialize is the orchestrator. It walks the Registry slots, assigns the
// constructed components into an AppContext, loads saved API keys, and (if a
// "brave" key is present) pushes it into the configured BraveKeyLoader.
//
// reg may be the zero value Registry — DefaultRegistry is substituted in that
// case so callers don't have to thread one through.
func Initialize(cfg Config, reg Registry) (*AppContext, error) {
	if !registryHasAnySlot(reg) {
		reg = DefaultRegistry()
	}

	cfg = cfg.withDefaults()

	ctx := &AppContext{}

	// Core managers. Each assignment tolerates a nil return from the
	// constructor — the stub registry returns nil for every component that
	// would normally need a real backend.
	ctx.MemoryManager = constructAs[MemoryManager](reg.MemoryManager, cfg)
	ctx.MemoryVector = constructAs[MemoryVector](reg.MemoryVector, cfg)
	ctx.MemoryProviderRegistry = constructAs[MemoryProviderRegistry](reg.MemoryProviderRegistry, cfg)
	ctx.SkillsManager = constructAs[SkillsManager](reg.SkillsManager, cfg)
	ctx.SessionManager = constructAs[SessionManager](reg.SessionManager, cfg)
	ctx.UploadHandler = constructAs[UploadHandler](reg.UploadHandler, cfg)
	ctx.PersonalDocsManager = constructAs[PersonalDocsManager](reg.PersonalDocsManager, cfg)
	ctx.APIKeyManager = constructAs[APIKeyManager](reg.APIKeyManager, cfg)
	ctx.PresetManager = constructAs[PresetManager](reg.PresetManager, cfg)
	ctx.ChatProcessor = constructAs[ChatProcessor](reg.ChatProcessor, cfg)
	ctx.ResearchHandler = constructAs[ResearchHandler](reg.ResearchHandler, cfg)
	ctx.ChatHandler = constructAs[ChatHandler](reg.ChatHandler, cfg)
	ctx.ModelDiscovery = constructAs[ModelDiscovery](reg.ModelDiscovery, cfg)

	if ctx.PersonalDocsManager != nil {
		ctx.PersonalIndex = ctx.PersonalDocsManager.Index()
	}
	if ctx.PresetManager != nil {
		ctx.CurrentPresets = ctx.PresetManager.List()
	}

	// Load saved API keys. This is the only side-effect Initialize performs
	// outside of constructing components — it mirrors the Python module's
	// final block.
	if ctx.APIKeyManager != nil {
		saved := ctx.APIKeyManager.Load()
		if key, ok := saved[BraveProvider]; ok && reg.BraveKeyLoader != nil {
			if err := reg.BraveKeyLoader.UpdateSearchConfig(key); err != nil {
				return ctx, fmt.Errorf("appinit: brave key loader: %w", err)
			}
		}
	}

	return ctx, nil
}

// registryHasAnySlot reports whether reg has at least one populated slot.
// Zero-value registries are promoted to DefaultRegistry to keep the call site
// terse.
func registryHasAnySlot(reg Registry) bool {
	return reg.MemoryManager != nil ||
		reg.MemoryVector != nil ||
		reg.MemoryProviderRegistry != nil ||
		reg.SkillsManager != nil ||
		reg.SessionManager != nil ||
		reg.UploadHandler != nil ||
		reg.PersonalDocsManager != nil ||
		reg.APIKeyManager != nil ||
		reg.PresetManager != nil ||
		reg.ChatProcessor != nil ||
		reg.ResearchHandler != nil ||
		reg.ChatHandler != nil ||
		reg.ModelDiscovery != nil ||
		reg.BraveKeyLoader != nil
}

// constructAs invokes c (when non-nil) and type-asserts the result. A nil
// constructor or a nil return both yield the zero value of T — the
// orchestrator treats both cases as "this component is unavailable".
func constructAs[T any](c ConstructorFunc, cfg Config) T {
	var zero T
	if c == nil {
		return zero
	}
	v, err := c(cfg)
	if err != nil || v == nil {
		return zero
	}
	if t, ok := v.(T); ok {
		return t
	}
	return zero
}
