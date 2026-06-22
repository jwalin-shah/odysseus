# context_compactor (Go port)

Go port of [`src/context_compactor.py`](../../src/context_compactor.py). The
Python module auto-compacts conversation history when approaching a model's
context window — it summarizes older turns via the same LLM, then prepends a
single `[Conversation summary ...]` system message in front of the recent
half so the conversation continues seamlessly.

The Go port keeps the same public contract but lives in its own module so it
can be reused without pulling in the whole Odysseus Flask app. It has **zero
external dependencies** and no I/O: the caller injects the LLM call, the
endpoint resolver, the session surface, and the token estimator via the
`Deps` struct.

## What this package does

`contextcompactor.TrimForContext` is the synchronous trimmer: it shrinks a
message list down to fit a model's context window by progressively dropping
RAG/memory system messages, then older conversation turns, then truncating a
single oversized current message with a visible notice.

`contextcompactor.MaybeCompact` is the async summarizer: when usage crosses
85% of the model's context window, it splits the conversation at the
midpoint, asks the injected LLM call to summarize the older half, and
returns a new history with the summary prepended.

The helpers below those two (`ContentAsText`, `SanitizeToolMessages`,
`MessageTextTokenEstimate`, `TruncateTextToTokenBudget`,
`TruncateMessageToTokenBudget`, `TruncateToolCallArgs`) are the same
building blocks the Python version uses internally and are exported so
callers can compose them into their own compaction flows.

## Layout

```
go-src/context_compactor/
  go.mod                       # module github.com/odysseus/context_compactor, go 1.22
  README.md                    # this file
  pkg/contextcompactor/
    messages.go                # Message type, constants, ContentAsText, sanitization, truncation, TrimForContext
    compactor.go               # Deps, SessionLike, HistoryReplacer, MaybeCompact, estimateContextLength, updateSessionHistory
    compactor_test.go          # table-driven tests for every exported function + race-clean fake session
  cmd/contextcompactor-demo/
    main.go                    # loads a fixture, runs TrimForContext, exercises MaybeCompact against an offline stub
```

## Mapping (Python → Go)

| Python (`src/context_compactor.py`)         | Go (`github.com/odysseus/context_compactor/pkg/contextcompactor`) |
| ------------------------------------------- | ----------------------------------------------------------------- |
| `COMPACT_THRESHOLD = 0.85`                  | `CompactThreshold`                                                |
| `SUMMARY_MAX_TOKENS = 1024`                 | `SummaryMaxTokens`                                                |
| `SMALL_CONTEXT_LIMIT = 8192`                | `SmallContextLimit`                                               |
| `SELF_SUMMARY_SYSTEM_PROMPT` (str const)    | `SelfSummarySystemPrompt` (var, runtime-replaced placeholders)    |
| `_content_as_text(content)`                 | `ContentAsText(content any) string`                               |
| `_sanitize_tool_messages(msgs)`             | `SanitizeToolMessages(msgs []Message) []Message`                  |
| `_message_text_token_estimate(text)`        | `MessageTextTokenEstimate(text string) int`                       |
| `_truncate_text_to_token_budget(text, ...)` | `TruncateTextToTokenBudget(text string, budget int) string`       |
| `_truncate_tool_call_args(msg, budget)`     | `TruncateToolCallArgs(msg Message, budget int) Message`           |
| `_truncate_message_to_token_budget(msg, …)` | `TruncateMessageToTokenBudget(msg Message, budget int) Message`   |
| `trim_for_context(messages, ctx, reserve)`  | `TrimForContext(msgs []Message, ctxLength, reserve, estimate) []Message` |
| `maybe_compact(session, url, model, …)`     | `MaybeCompact(ctx, session, msgs, deps) ([]Message, int, bool)`   |
| `_update_session_history(session, …)`       | `updateSessionHistory(...)` (internal — driven by `MaybeCompact`) |
| `estimate_tokens` (from `src.model_context`)| injected via `Deps.EstimateTokens` (`EstimateTokensFn`)           |
| `llm_call_async(...)`                       | injected via `Deps.LLMCall` (`LLMCallFn`)                          |
| `resolve_endpoint("utility", owner=…)`      | injected via `Deps.ResolveEndpoint` (`ResolveEndpointFn`)         |
| `core.models.ChatMessage`, session.manager  | abstracted behind `SessionLike` + `HistoryReplacer` interfaces     |

The Go port is intentionally message-agnostic. `Message` is an alias for
`map[string]any` so it can carry the same shape the rest of the system
already speaks (OpenAI-style `{role, content, tool_calls, metadata, …}`).
The Python `ChatMessage` dataclass and the `core.models` session manager
become small interfaces the caller implements in one method.

## Public API

```go
import (
    "context"

    contextcompactor "github.com/odysseus/context_compactor/pkg/contextcompactor"
)

// Synchronous trim — pure function over the message list.
trimmed := contextcompactor.TrimForContext(messages, 8192, 512, myEstimate)

// Async compaction — caller wires up the LLM, resolver, and session.
type Deps struct {
    EstimateTokens  EstimateTokensFn  // optional; falls back to defaultEstimateTokens
    LLMCall         LLMCallFn         // optional; nil ⇒ MaybeCompact is a no-op
    ResolveEndpoint ResolveEndpointFn // optional; falls back to EndpointURL/Model
    HistoryReplacer HistoryReplacer   // optional; nil ⇒ skips persistence
    Owner           string
    EndpointURL     string
    Model           string
    Headers         map[string]string
}

msgs, ctxLen, wasCompacted := contextcompactor.MaybeCompact(
    context.Background(), sess, messages, deps,
)
```

`SessionLike` is the minimal surface `MaybeCompact` reads from a session:

```go
type SessionLike interface {
    History() []Message
    SetHistory([]Message)
    ID() string
}
```

`HistoryReplacer` is the optional persistent-storage hook:

```go
type HistoryReplacer interface {
    ReplaceMessages(sessionID string, msgs []Message) bool
}
```

## Design choices

- **Pure functions, no globals.** All state lives in the caller's hand.
  That matches the spirit of the Python version, where `maybe_compact`
  reads the session but does not own any module-level state.
- **`Message = map[string]any`.** It is the simplest faithful translation
  of Python's `Dict[str, Any]` and lets callers keep the OpenAI-style
  shape (`role`, `content`, `tool_calls`, `metadata`, `_protected`,
  `research_spinoff_from`) without a struct rewrite. The Python source
  already passes messages as dicts end-to-end.
- **Dependency injection over imports.** The Python version imports
  `src.model_context.estimate_tokens`, `src.llm_core.llm_call_async`, and
  `src.endpoint_resolver.resolve_endpoint` directly. The Go port cannot —
  the corresponding Go packages live elsewhere (`go-src/llm_core` etc.) and
  wiring through them would pull in the whole stack. Instead, callers pass
  function-typed dependencies via `Deps`, identical to how `rate_limiter`'s
  clock injection works.
- **`EstimateTokensFn` is required (or defaulted).** If the caller does not
  supply one, the package falls back to a rough chars * 0.3 estimate plus
  per-message overhead. This is good enough for the threshold check and the
  drop-oldest-t heuristic; callers that need accurate counts (e.g. to size
  a model exactly) should inject `src.model_context.estimate_tokens`'s
  Go equivalent.
- **`MaybeCompact` degrades gracefully.** When the LLM call fails, the
  function returns the original messages with `wasCompacted=false`. The
  caller's own `TrimForContext` pass then handles length. The Python
  source does the same thing; the Go port preserves it.

## Out of scope

- **No Flask / DB / HTTP wiring.** The Python source accepts a `session`
  object and reads/writes via `core.models.get_session_manager_instance`.
  The Go port stays decoupled: it accepts `SessionLike` and
  `HistoryReplacer` interfaces and leaves the persistence layer to the
  caller (typically `routes/chat_routes.py` translated to a Go HTTP
  handler).
- **No real LLM call.** The demo binary sets `LLMCall = nil`, which makes
  `MaybeCompact` a no-op that just returns the original messages plus
  `wasCompacted=false`. Wiring a real call is a one-liner — implement
  `LLMCallFn` to forward to `llm_core.CallAsync` — but is out of scope
  for an offline demo.
- **No endpoint resolution.** `resolve_endpoint("utility", owner=...)` is
  injected as a `ResolveEndpointFn`. The fallback when the resolver is
  nil is to use the supplied `Deps.EndpointURL` / `Deps.Model`.
- **No model context length lookup.** `get_context_length(endpoint_url,
  model)` lives in `src/model_context.py`. The Go port returns
  `SmallContextLimit` (8192) when no resolver is supplied so the threshold
  check stays well-defined. Production callers inject the resolver.

## Running tests

```bash
cd go-src/context_compactor
go build ./...
go test -race ./...
go vet ./...
```

`compactor_test.go` is stdlib-only and exercises every exported function:

- `ContentAsText` — string / list of blocks / nil / empty list.
- `SanitizeToolMessages` — orphan tool messages dropped, valid tool batches
  preserved, dangling `tool_calls` stripped (with text retained when present).
- `MessageTextTokenEstimate` — empty / short / long.
- `TruncateTextToTokenBudget` — tiny budget returns the omission marker;
  larger budget keeps head + tail + notice; messages under budget are
  untouched.
- `TruncateToolCallArgs` — oversized `arguments` replaced with the
  `_truncated_for_context` placeholder; small calls and no-calls messages
  are unchanged.
- `TruncateMessageToTokenBudget` — string content, multimodal list
  content, and tool-only turns all truncate cleanly.
- `TrimForContext` — no-op under budget, drops RAG/memo system messages
  while keeping the preset, preserves research primers, drops older
  turns while keeping the current user turn, truncates an oversized
  current message with a visible notice.
- `MaybeCompact` — under-threshold returns `false`; over-threshold fires
  the LLM stub, prepends the summary, calls the replacer; LLM errors
  degrade gracefully; fewer than 4 conversation messages returns `false`.

## Demo CLI

```bash
cd go-src/context_compactor
go run ./cmd/contextcompactor-demo
```

The CLI loads a hard-coded fixture (system messages + 5 user/assistant
turns), runs `TrimForContext` against a 1200-token synthetic context
window, prints before/after token counts and a per-message outline, then
exercises `MaybeCompact` against an offline stub. No network is touched.

Sample output:

```
before: 1815 tokens (10 messages)
after:  952 tokens (5 messages)

--- post-trim outline ---
[00] system    You are a helpful assistant named Odysseus.
[01] user      Earlier question about authentication.
[02] assistant Earlier answer about OAuth flows.
[03] user      Middle question about caching.
[04] user      Current question: how do I roll back a bad release?

MaybeCompact: wasCompacted=false contextLength=8192 resultMessages=10
```
