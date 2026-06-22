# Odysseus agent_loop Go port

Wave-4 port of `src/agent_loop.py` (3,190 LOC) into a small Go module.

## Scope

The Python source is a streaming multi-round agent loop tightly coupled to
FastAPI, ChromaDB, httpx, MCP, plan-mode state, fallback endpoints, RAG
retrieval, and dozens of helper modules. This port covers the **public
surface** and the **streaming loop signature**; provider-specific bits
(LLM client, tool implementations, MCP manager, RAG index, ChromaDB) are
abstracted behind interfaces and stubs.

The port is the largest single wave-4 port by source LOC — most of the work
went into identifying what to keep, what to stub, and where the cut lines
land. See the table below.

## Module layout

```
go-src/agent_loop/
├── go.mod                 # module github.com/odysseus/agent_loop (Go 1.22)
├── README.md              # this file
├── cmd/agentloop/main.go  # demo CLI: 2-round fake-LLM loop
└── pkg/agentloop/
    ├── types.go           # Event, ToolCall, Message, Metrics
    ├── loop.go            # Stream() entry point + runStream driver
    ├── prompt.go          # AssemblePrompt + sectionText
    ├── classify.go        # ClassifyAgentRequest + keyword table
    ├── verifier.go        # RunVerifierSubagent (STUB)
    ├── verifier_helpers.go
    ├── runaway.go         # DetectRunawayCall
    ├── metrics.go         # ComputeFinalMetrics + ComputeFinalMetricsFromStream
    ├── tools.go           # ToolBlocks / AppendToolResults / TruncateToolOutput
    ├── loop_test.go       # streaming loop tests
    ├── prompt_test.go
    ├── classify_test.go
    ├── runaway_test.go
    └── metrics_test.go
```

## Public surface

```go
type Event interface{ eventTag() string }
type TextChunk struct{ Delta string }
type RoundMarker struct{ Round int }
type ToolCall struct{ ID string; Name string; Args json.RawMessage }
type ToolResult struct{ ID string; Output string; IsError bool }
type Final struct{ Metrics Metrics }

type Message struct{ Role, Content string }
type Metrics struct{ /* token counts, rounds, tool calls, cancelled, ... */ }

type Config struct {
    Model string
    Tools []Tool
    Provider Provider
    MaxRounds int           // default 10
    Timeout   time.Duration // default 120s
    Owner string
    Compact bool
    DisabledTools map[string]bool
    Logger *slog.Logger
}

type Request struct {
    SessionID string
    Messages  []Message
    Config    Config
}

func Stream(ctx context.Context, req Request) (<-chan Event, <-chan error)
```

## Stub vs ported inventory

Each row is one Python symbol. "Status" is one of:

- **PORTED** — the Go function has the same signature and the documented behavior
  matches the Python behavior.
- **PORTED-STUB** — the Go function returns a canned result; wiring to a real
  LLM/tool/MCP/RAG source is intentionally out of scope.
- **OMITTED** — the Python symbol is not represented in the Go port; the
  Python helper is referenced by other modules (`stream_agent_loop`,
  `_compute_final_metrics`) that are also stubbed.

| Python symbol                       | Status        | Go location              |
|---|---|---|
| `stream_agent_loop`                 | PORTED        | `loop.go` Stream/runStream |
| `_assemble_prompt`                  | PORTED        | `prompt.go` AssemblePrompt |
| `_build_system_prompt`              | OMITTED       | folded into AssemblePrompt |
| `_classify_agent_request`           | PORTED        | `classify.go` ClassifyAgentRequest |
| `_is_explicit_continuation`         | PORTED        | `classify.go` isExplicitContinuation |
| `_assistant_requested_followup`     | PORTED        | `classify.go` assistantRequestedFollowup |
| `_recent_context_for_retrieval`     | OMITTED       | RAG-only, not in scope |
| `_detect_admin_intent`              | OMITTED       | not part of the public spec |
| `_extract_last_user_message`        | PORTED        | inlined in classify.go |
| `_resolve_tool_blocks`              | OMITTED       | provider's responsibility |
| `_append_tool_results`              | PORTED (simplified) | `tools.go` AppendToolResults |
| `_compute_final_metrics`            | PORTED        | `metrics.go` ComputeFinalMetrics |
| `_build_actions_snapshot`           | OMITTED       | verifier-only, stubbed |
| `_run_verifier_subagent`            | PORTED-STUB   | `verifier.go` RunVerifierSubagent |
| `_empty_response_fallback`          | OMITTED       | not part of the public spec |
| `build_active_plan_note`            | OMITTED       | plan-mode, not in scope |
| `_detect_runaway_call`              | PORTED        | `runaway.go` DetectRunawayCall |
| `_domain_rules_for_tools`           | OMITTED       | simplified into AssemblePrompt |
| `_section_text`                     | PORTED        | `prompt.go` sectionText |
| `_load_mcp_disabled_map`            | OMITTED       | DB-bound, out of scope |
| `_LOW_SIGNAL_RE`                    | PORTED        | `classify.go` lowSignalRE |
| `_EXPLICIT_CONTINUATION_RE`         | PORTED        | `classify.go` explicitContinuationRE |
| `_is_ollama_openai_compat_url`      | OMITTED       | provider-routing concern |
| `_endpoint_lookup_keys`             | OMITTED       | provider-routing concern |
| `get_builtin_overrides`             | OMITTED       | DB-bound, out of scope |
| `MAX_AGENT_ROUNDS`                  | PORTED (default 10) | Config.applyDefaults |
| `TOOL_SECTIONS`                     | PORTED (subset)    | `prompt.go` toolSections |

### Stubs called out

- **Verifier** — Python's `_run_verifier_subagent` dispatches a second LLM
  call with no shared history and asks it to judge whether the agent's
  actions satisfy the request. The Go stub returns `{OK: true, Notes: "stub"}`
  after 10ms simulated latency. Marked `PORTED-STUB` in the source.

- **Prompt section table** — the Python `TOOL_SECTIONS` dictionary has
  dozens of entries (one per tool, with prose examples). The Go port ships a
  small representative subset (bash, web_search, web_fetch, read_file,
  write_file, create_document, edit_document, manage_calendar, manage_notes,
  manage_memory, list_emails, send_email) and falls back to
  `[no section: <name>]` for the rest, matching the spec's "missing
  sections get a default" rule.

- **RAG / tool retrieval / ChromaDB** — Python's `_recent_context_for_retrieval`,
  `src.tool_index`, and ChromaDB lookups are intentionally absent. The Go
  port runs only with the caller-provided `Config.Tools`.

- **MCP / plan mode / fallback endpoints** — the Python loop branches on
  `mcp_mgr`, `plan_mode`, `fallbacks`, and `tool_policy`. The Go port treats
  `Config.Tools` as already-resolved and `Config.DisabledTools` as the only
  filtering mechanism.

## Validation

From this directory:

```bash
go mod tidy
go build ./...
go test -race ./...
go vet ./...
```

All pass at the time of writing. Test count: 16 tests covering happy paths,
cancellation, max-rounds cap, runaway detection, prompt assembly, classifier
modes, and metric aggregation.

## Running the demo CLI

```bash
go run ./cmd/agentloop
```

Outputs streaming text chunks, a single bash tool call + result, then a Final
event with rounds=2, tools=1, output_tokens=N, cancelled=false.

## Blockers / open questions

- The Python `_classify_agent_request` returns a richer dict (low_signal,
  continuation, domains, retrieval_query). The Go port collapses these to
  `{Mode, Confidence, Reason}` per the public spec. If a future caller needs
  `domains`, the Go `Reason` string is the only available carrier — wire a
  real `Domains []string` field if you need it machine-readable.

- The Python `_compute_final_metrics` accepts ~12 named arguments. The Go
  port collapses to `[]Event` + `time.Duration`. Provider-reported
  input/output token counts are not surfaced; for exact counts wire a
  Provider that emits `TextChunk` sized to the underlying token count.

- The Python tool-output truncation helper delegates to
  `src.tool_utils._truncate` (10 000 chars cap, suffix "...
  (truncated, N chars total)"). The Go port re-implements the same rule in
  `tools.go` TruncateToolOutput — no shared logic with Python.