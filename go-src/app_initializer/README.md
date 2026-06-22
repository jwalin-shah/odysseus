# app_initializer (Go port)

Go port of `src/app_initializer.py`. The Python module is an orchestrator: it
creates a fixed set of directories and then constructs a graph of ~13
managers/handlers (memory, skills, session, upload, personal_docs, api_keys,
presets, chat_processor, research_handler, chat_handler, model_discovery,
memory_vector, memory_provider_registry). The Go port captures that public
surface behind interfaces so the same orchestrator runs in production with
real backends and in tests with no-op stubs.

## Scope

This package does NOT re-implement every backing manager. The real
implementations (FastAPI handlers, ChromaDB vector store, MCP providers)
stay in their respective Python or Go packages. This port only provides:

- **Interfaces** for each component the orchestrator touches.
- **A `Config` struct** holding paths and a base directory.
- **A `Registry`** that lets callers inject constructor functions per slot.
- **`CreateDirectories` / `Initialize`** — the two entry points from the
  Python module.
- **`AppContext`** — the struct that mirrors the dict the Python
  `initialize_managers` function returns.
- **`BraveKeyLoader`** — the tiny surface used to push a loaded "brave"
  key into the search subsystem.
- **A default JSON-backed `APIKeyManager`** so the Brave-key wiring is
  testable without a crypto dependency.

## Layout

```
go-src/app_initializer/
  go.mod                 # module github.com/odysseus/app_initializer
  go.sum
  README.md
  cmd/appinit/main.go    # demo CLI: --data-dir, --personal-dir, ...
  pkg/appinit/
    constants.go         # Default* path constants + BraveProvider
    config.go            # Config struct, WithDefaults, RequiredDirectories
    registry.go          # Registry + DefaultRegistry + ConstructorFunc
    manager_interfaces.go # one interface per component
    api_keys_backend.go  # stdlib JSON backend for APIKeyManager
    initialize.go        # CreateDirectories + Initialize + AppContext
    initialize_test.go   # full coverage of the public surface
```

## Why interfaces

The Python module constructs concrete classes that each have their own
heavyweight backend (FastAPI app, ChromaDB client, MCP registry, ...). In
Go, those backends are usually separate modules. Wiring the orchestrator to
concrete types would force `Initialize` to import the world.

Instead, `Registry` holds `ConstructorFunc` slots keyed by component. A
constructor takes a `Config` and returns the component as `any`; `Initialize`
type-asserts it back to the matching interface and stores it in `AppContext`.
The default registry wires:

- a **real** `JSON`-backed `APIKeyManager` (so the Brave-key loader path is
  exercisable end-to-end), and
- **no-op stubs** (`return nil, nil`) for everything else.

Tests substitute individual slots to assert specific behaviour without
spinning up FastAPI, Chroma, or MCP.

## Public API

```go
cfg := appinit.Config{DataDir: "/tmp/data"} // empty fields → defaults

if err := appinit.CreateDirectories(cfg); err != nil { /* ... */ }

ctx, err := appinit.Initialize(cfg, appinit.Registry{}) // zero-value → defaults
if err != nil { /* ... */ }
_ = ctx.MemoryManager      // nil with default registry (stub)
_ = ctx.APIKeyManager      // *jsonAPIKeyManager — real backend
_ = ctx.PersonalIndex      // []map[string]any
_ = ctx.CurrentPresets     // []map[string]any
```

## Port notes

- **`APIKeyManager` is plaintext JSON, not Fernet.** The Python
  implementation uses `cryptography.Fernet` to encrypt the on-disk dict. We
  chose stdlib-only for this port to keep dependencies minimal. The real prod
  port would add a `crypto/...` wrapper; this backend is sufficient for
  orchestrator tests.
- **`MemoryVector` and `MemoryProviderRegistry` are optional.** The Python
  code wraps their construction in `try/except` because Chroma may be
  unavailable. The Go port preserves that optionality: a Registry slot that
  returns `nil` is treated as "component absent" and `AppContext` leaves the
  field zero.
- **Atomic writes for `api_keys.json`.** The JSON backend uses
  `os.CreateTemp` + `os.Rename` so a crash mid-write cannot corrupt the file.
- **The Brave key path** is wired exactly as the Python module wires it:
  load saved keys, look up `"brave"`, push the plaintext key into the
  configured `BraveKeyLoader`. The default loader is a no-op; tests pass a
  recording stub.

## Running tests

```bash
cd go-src/app_initializer
go build ./...
go test -race ./...
```

All tests use `t.TempDir()` and avoid network/DB dependencies.

## Demo CLI

```bash
go run ./cmd/appinit \
  --data-dir /tmp/x/data \
  --personal-dir /tmp/x/personal \
  --runbook-dir /tmp/x/runbook \
  --upload-dir /tmp/x/uploads \
  --base-dir /tmp/x
```

The CLI creates the four directories, runs `Initialize`, and prints a
summary of which components were wired. With the default registry, every
component except `api_key_manager` shows up as `<nil>`.