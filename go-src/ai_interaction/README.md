# ai_interaction (Go port)

Go port of `src/ai_interaction.py` — the orchestrator for the AI tool
calls the chat agent invokes: `pipeline`, `manage_memory`, `manage_rag`,
`ui_control`, and `generate_image`.

The Python source is a single 1100+ line module that:

- parses tool-call payloads (`do_pipeline`, `do_manage_memory`,
  `do_manage_rag`, `do_ui_control`, `do_generate_image`),
- dispatches the parsed payload against Flask/SQLAlchemy/ChromaDB/HTTP
  runtime deps,
- exposes both sync (`dispatch_ai_tool`) and SSE streaming
  (`stream_ai_tool`) entry points,
- owns the `_resolve_model` model/endpoint resolution dance.

The Go port preserves the same dict-shaped return values via a
`ToolResult` struct and a `*Request` parser output per tool, and replaces
the live Flask/SQLAlchemy/ChromaDB deps with injected interfaces. The
runtime can wire the real implementations in production and substitute
in-memory stubs in tests.

## Layout

```
ai_interaction/
├── go.mod
├── README.md
├── pkg/aiinteraction/
│   ├── constants.go        # timeouts, presets, fallback lists
│   ├── types.go            # PipelineStep, MemoryAction, RAGAction, ...
│   ├── pipeline.go         # ParsePipelineSteps, ValidatePipelineSteps, ...
│   ├── memory.go           # ParseMemoryAction, FormatMemoryList, ...
│   ├── rag.go              # ParseRAGAction, ExpandDirectory, ...
│   ├── uicontrol.go        # ParseUIControlAction + per-action event builders
│   ├── image.go            # ParseImageRequest, ClassifyImageModel, ...
│   ├── model.go            # ParseModelSpec, BuildChatURL, BuildHeaders
│   ├── resolver.go         # ResolveModel, ResolveOptions, LLMCall
│   ├── interfaces.go       # HTTPDoer, LLMCall, MemoryStore, ...
│   ├── dispatch.go         # RunPipeline, RunManageMemory, ...
│   ├── dispatcher.go       # DispatchTool, StreamTool
│   ├── base64.go, config.go, env.go, json.go  # helpers
│   ├── model_test.go       # table-driven coverage of resolver/url helpers
│   └── extras_test.go      # table-driven coverage of the remaining APIs
└── cmd/aiinteraction-demo/
    └── main.go             # walks the entire public surface
```

## Public API at a glance

```go
// Parsers
func ParsePipelineSteps(content string) (*PipelineRequest, error)
func ParseMemoryAction(content string) (*MemoryAction, error)
func ParseRAGAction(content string) (*RAGAction, error)
func ParseUIControlAction(content string) (*UIControlAction, error)
func ParseImageRequest(content string) (*ImageRequest, error)
func ParseModelSpec(spec string) (ModelSpec, error)

// Drivers (mirror do_pipeline, do_manage_memory, do_manage_rag,
// do_ui_control, do_generate_image)
func RunPipeline(req *PipelineRequest, resolver ModelResolver, llm LLMCall) (ToolResult, error)
func RunManageMemory(content string, store MemoryStore, vec MemoryVector, bus EventBus, owner string) (ToolResult, error)
func RunManageRAG(content string, rag RAGManager, pdocs PersonalDocsManager) (ToolResult, error)
func RunUIControl(content string, opts UIControlOptions) (ToolResult, error)
func RunGenerateImage(content string, opts ImageOptions) (ToolResult, error)

// Resolver + URLs
func ResolveModel(model string, opts ResolveOptions) (ResolvedModel, error)
func BuildChatURL(base string) string
func BuildModelsURL(base string) string
func BuildHeaders(apiKey, base string) map[string]string

// Dispatch (sync + streaming — mirrors dispatch_ai_tool / stream_ai_tool)
func DispatchTool(name, content, sessionID, owner string, deps DriverDeps) (string, ToolResult)
func StreamTool(name, content, sessionID, owner string, deps DriverDeps) <-chan StreamEvent
```

## Demo

```
go run ./cmd/aiinteraction-demo
```

Output (abbreviated):

```
== aiinteraction demo ==

[1] pipeline: parse + validate
  format=json steps=2
  format=lines steps=2
  result.results: # Pipeline Results (2 steps) ## Step 1: gpt-4 *Instruction: draft*  ...
  steps=2 final="stub output for gpt-4"

[2] manage_memory: add / list / search
  add: Memory added: [fact] likes coffee
  list: Found 1 memory entries: ...

[3] manage_rag: list / add_directory
  list: **Indexed directories (1):**
    - `/notes`
  expand: ~/notes -> /Users/<you>/notes

[4] ui_control: toggle / set_mode / open_panel / open_email_reply
  toggle shell on                                    -> Toggle 'bash' set to on
  set_mode chat                                      -> Mode changed to 'chat'
  open_panel memories                                -> Opening memories panel
  open_email_reply 42 INBOX reply Sounds good...     -> Opening reply draft for email UID 42 ...

[5] generate_image: parse + classify
  prompt="a foggy mountain at dawn" model=gpt-image-1 size=1536x1024 quality=high
  classifier: gpt=true dalle=false local=false

[6] model spec + dispatch
  spec={ModelName:claude-sonnet-4 EndpointName:my-endpoint}
  desc="ui_control: highlight .chat-bubble New message" result.results="Highlighting '.chat-bubble'"

[7] stream: one final event
  final=true desc="pipeline: running steps" ...
```

## Injected interfaces

The Python source reaches into module-level singletons
(`session_manager`, `memory_manager`, `rag_manager`, `personal_docs`,
`gallery`, etc.) and into the live `requests` HTTP client. The Go port
collapses each of those into an explicit interface so callers can wire
real implementations in production and stand-ins in tests:

| Interface | Replaces |
| --- | --- |
| `HTTPDoer` | the chat-completions / models GET calls |
| `LLMCall` | `llm_core.chat` (function-typed, no interface) |
| `MemoryStore` / `MemoryVector` | the in-memory dict + ChromaDB collection |
| `RAGManager` / `PersonalDocsManager` | `personal_docs.index_personal_documents` |
| `GalleryWriter` | the SQLite-backed generated-images writer |
| `SessionManager` | the global session manager singleton |
| `ModelEndpointStore` / `EndpointRuntimeResolver` / `ModelResolver` | the admin endpoint store + runtime secrets resolver |
| `EventBus` | the WS broadcast bus |
| `PrefsStore` | the prefs JSON |
| `URLSafetyChecker` / `ImageTransport` / `ImageFileWriter` | the outbound HTTP fetch + file write + URL allowlist |

Any of these can be left nil in the demo / test setup; the drivers
short-circuit to the appropriate "manager not available" / "no
endpoint configured" error message.

## ToolResult shape

The Python source emits dicts of the form `{"results": "..."}` on
success and `{"error": "..."}` on failure. The Go port carries the same
fields as exported struct fields:

```go
type ToolResult struct {
    Results     string                 `json:"results,omitempty"`
    Error       string                 `json:"error,omitempty"`
    Action      string                 `json:"action,omitempty"`
    Steps       []PipelineStepOutput   `json:"steps,omitempty"`
    FinalOutput string                 `json:"final_output,omitempty"`
    ImageURL    string                 `json:"image_url,omitempty"`
    ImageID     string                 `json:"image_id,omitempty"`
    MemoryID    string                 `json:"memory_id,omitempty"`
    Directory   string                 `json:"directory,omitempty"`
    Extra       map[string]any         `json:"-"`
}
```

Field tags match the Python dict shape, so callers that round-trip
JSON don't need translation. `Extra` carries per-action payloads
(e.g. the UI control event body) as a free-form map.

## Streaming

`StreamTool` returns a channel of `StreamEvent{Final bool, Desc string,
Result ToolResult}`. The channel closes after the terminal event; the
SSE handler in production reads it the same way it reads
`stream_with_tool`.

## Validation

```
go build ./...
go test -race ./...
go vet ./...
```

All three pass on Go 1.22 with no external dependencies.
