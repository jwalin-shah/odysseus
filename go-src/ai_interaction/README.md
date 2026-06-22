# ai_interaction (Go port)

A Go 1.22+ port of `src/ai_interaction.py` from the upstream Python
monorepo. The Python module is the agent-side dispatcher for the
"AI interaction" tool group (pipeline, memory, RAG, UI control, image
generation); this port preserves the same surface, but moves the
HTTP-coupled bits behind explicit interfaces so it can be tested
without a network, a real model server, or a real `~/` directory.

## Layout

```
go-src/ai_interaction/
  go.mod                     module github.com/odysseus/ai_interaction
  README.md                  this file
  cmd/aiint/main.go          demo CLI: stdin JSON commands -> stdout JSON results
  pkg/aiint/
    types.go                 constants + Result shape
    manager_interfaces.go    Manager struct + dependency-injection seams
    pipeline.go              ParsePipeline + FormatPipelineMarkdown
    pipeline_test.go         11 tests
    manage_memory.go         memory list/add/edit/delete/search
    manage_memory_test.go    15 tests
    manage_rag.go            RAG list/add_directory/remove_directory
    manage_rag_test.go       12 tests
    ui_control.go            toggle/set_mode/switch_model/set_theme/create_theme/
                             highlight/clear_highlight/open_panel/
                             open_email_reply/get_toggles
    ui_control_test.go       ~22 tests
    dispatch.go              Dispatch(tool, content, mgr)
    dispatch_test.go         11 tests
```

## Public API

The package is `github.com/odysseus/ai_interaction/pkg/aiint`.

- `Dispatch(tool, content string, mgr *Manager) (description string, result *Result, err error)`
  - Single entry point mirroring Python's `dispatch_ai_tool`. Pure
    routing — handlers do the real work and report success/failure
    via `Result.OK` + `Result.Error`. Only `generate_image` returns a
    real Go error (`ErrUnsupported`) when the runner isn't wired.
- `ParsePipeline(content string) ([]PipelineStep, error)`
- `FormatPipelineMarkdown(steps []PipelineStep, outputs []string) string`
- `ManageMemory(content string, mgr MemoryManager, vec MemoryVector, owner string) (*Result, error)`
- `ManageRAG(content string, mgr *Manager) (*Result, error)`
- `UIControl(content string, mgr *Manager, themes []string) (*Result, error)`

### Result shape

```go
type Result struct {
    OK      bool           `json:"ok"`
    Action  string         `json:"action,omitempty"`
    Results string         `json:"results,omitempty"`
    Error   string         `json:"error,omitempty"`
    Details map[string]any `json:"details,omitempty"`
}
```

`Details` keeps the Python `dict` shape — handlers populate the
keys the original Python module emitted (e.g. `toggle_name`,
`panel`, `steps`, `final_output`, `image_url`).

### Constants

| Go name | Value | Mirrors |
|---|---|---|
| `AIChatTimeout` | `120 * time.Second` | `AI_CHAT_TIMEOUT = 120` |
| `MaxDebateRounds` | `5` | `MAX_DEBATE_ROUNDS = 5` |
| `MaxPipelineSteps` | `10` | `MAX_PIPELINE_STEPS = 10` |
| `MaxPipelineOutputBytes` | `5000` | internal truncation |

## Manager (dependency injection)

Python's module used module-level globals (a single
`_memory_manager`, a single `_rag_manager`, a single
`_personal_docs_manager`, a single `_session_manager`, a single
`MODEL_RESOLVE_URL`, and a single `AI_CHAT_URL`). The Go port
removes those globals. Callers wire dependencies into a `Manager`
struct and pass that struct into every handler:

```go
mgr := &aiint.Manager{
    Memory:        myMemoryMgr,    // optional
    MemoryVector:  myVector,       // optional, only used by manage_memory
    RAG:           myRagMgr,       // required for manage_rag
    PersonalDocs:  myPDocs,        // required for manage_rag list
    Resolver:      myModelResolve, // required for ui_control.switch_model + pipeline
    LLM:           myLLM,          // required for pipeline
    Image:         myImageGen,     // required for generate_image (else ErrUnsupported)
    Sessions:      nil,            // reserved for future session writes
    HomeDir:       os.UserHomeDir, // injectable for tests
}
```

The interfaces are intentionally narrow so tests can substitute
counting stubs in place of real services. See the test files for
`stubRAG`, `stubPDocs`, `stubResolver`, and the in-package
`newMemMgr` helper.

## Port notes

1. **Globals -> injection.** Every global in the Python module has a
   matching interface in `manager_interfaces.go`. Tests pass stubs;
   production callers wire their own implementations.

2. **HTTP-coupled bits live behind interfaces.** Model resolution,
   chat completion, and image generation are all abstracted
   (`ModelResolver`, `LLMRunner`, `ImageRunner`). The Python module's
   in-place HTTP calls and SQL writes are not in this port.

3. **Pure-parsing bits ported in full.** `ui_control` is a deterministic
   parser/state-machine: it ports every action, alias, panel, theme
   preset, hex-color rule, and bgPattern verbatim. `pipeline.go` and
   `manage_rag.go` are likewise pure.

4. **Ownership is preserved.** `manage_memory` accepts an `owner` arg;
   entries with a non-empty `Owner` that doesn't match the caller are
   reported as "not found" instead of leaking across users. Tests
   cover both happy and cross-owner paths.

5. **Errors stay in-band.** Python returned `{"ok": False, "error": "..."}`
   for normal validation failures. The Go port does the same via
   `Result{OK: false, Error: "..."}`. Only structurally unsupported
   tools (no runner wired) return a real Go error (`ErrUnsupported`)
   so the caller can branch on `errors.Is`.

6. **No filesystem, no network, no real `~/`.** Every test uses
   `t.TempDir()` for any path it touches, and `HomeDir` is injectable.

## Build & test

```bash
cd go-src/ai_interaction
go build ./...
go test -race ./...
```

The demo CLI:

```bash
echo '{"tool":"ui_control","content":"open_panel memories"}' | go run ./cmd/aiint
echo '{"tool":"ui_control","content":"create_theme mybrand #112233 #445566 #778899 #aabbcc #ddeeff bgPattern=dots frosted=true"}' | go run ./cmd/aiint
```

## Compatibility

The port targets Go 1.22 and uses only the standard library
(`context`, `encoding/json`, `errors`, `fmt`, `os`, `path/filepath`,
`regexp`, `strconv`, `strings`, `testing`, `time`).
