# assistant_log (Go port)

Go port of [`src/assistant_log.py`](../../src/assistant_log.py). The
Python module used to write system/task activity into a favorited
Assistant chat session; that surface has since moved to the Tasks /
notifications feeds, so the Python implementation has been reduced to a
debug-level no-op shim. This Go port keeps the same shim semantics so
the Python-to-Go porting effort produces a faithful translation.

The Python source:

```python
def set_session_manager(sm):
    global _session_manager
    _session_manager = sm

_LEGACY_TAG_RE = re.compile(r"^\s*\*\*\[([^\]]{1,40})\]\*\*\s*")

def log_to_assistant(owner, content, role="assistant", *, category=None):
    """Legacy no-op. Older builds wrote system/task activity into a
    favorited Assistant chat session. Activity now lives in Tasks/
    notifications, so keep this shim for callers while preventing
    sidebar-log sessions from being created or filled.
    """
    logger.debug("log_to_assistant ignored legacy activity category=%r owner=%r", category, owner)
    return
```

The Go port preserves the same shim semantics using a real `log/slog`
logger at debug level so the no-op is observable.

## Mapping (Python → Go)

| Python (`src/assistant_log.py`)        | Go (`github.com/odysseus/assistant_log/pkg/assistantlog`) |
|----------------------------------------|-----------------------------------------------------------|
| `log_to_assistant(owner, content, role, *, category)` | `LogToAssistant(ctx, LogOptions, *slog.Logger) Result` |
| `set_session_manager(sm)`              | `SetSessionManager(sm SessionManager)` |
| `_LEGACY_TAG_RE`                       | `LegacyTagRE` (also exposed via `ParseLegacyTag(s)`) |
| `logger.debug(...)`                    | `slog.DebugContext(ctx, msg, ...)` via injected `*slog.Logger` |

`LogToAssistant` is the modern Go entry point. The Python signature's
keyword-only `category` becomes an explicit `LogOptions.Category`
field. `Result` mirrors the Python module's `None` return value with a
small struct (`Logged`, `Reason`, `Category`) so callers can confirm
they hit the shim path.

The optional `*slog.Logger` argument is the wave-9 test-ergonomics
extension; passing `nil` falls back to `slog.Default()`. This lets
tests swap a `bytes.Buffer`-backed JSON handler without mutating the
process-wide default.

## Public surface

```go
import (
    "context"
    "log/slog"
    alog "github.com/odysseus/assistant_log/pkg/assistantlog"
)

// No-op shim; Logged is always false in this port.
res := alog.LogToAssistant(context.Background(), alog.LogOptions{
    Owner:   "alice",
    Content: "**[Download]** file.zip",
    Role:    "assistant", // optional; defaults to alog.DefaultRole
    // Category: "Manual", // optional; explicit override wins
}, nil)
fmt.Println(res.Logged, res.Reason, res.Category)

// SetSessionManager accepts any SessionManager. The shim never calls
// it, but the reference is kept so a future build that re-enables
// session logging has somewhere to route to.
type sm struct{}
func (sm) PostActivity(ctx context.Context, owner, role, content string, category *string) error { return nil }
alog.SetSessionManager(sm{})

// ParseLegacyTag extracts the "**[Category]**" prefix.
cat, rest, ok := alog.ParseLegacyTag("**[Download]** file.zip")
// cat == "Download", rest == "file.zip", ok == true

// LegacyTagRE is exposed for callers that prefer raw regex access.
match := alog.LegacyTagRE.FindStringSubmatch("**[Download]** file.zip")
```

## Design choices

- **Legacy no-op, not a re-implementation.** The Python module dropped
  activity on the floor; the Go port does the same. There is no real
  "post to chat session" path. Anything that needs activity logging
  should route through Tasks / notifications rather than revive this
  shim.
- **`*slog.Logger` parameter on `LogToAssistant`.** The wave-9 standing
  rules ask ports to expose an injectable logger so tests can assert on
  the emitted log line. Passing `nil` keeps the production call site
  one line; passing `slog.New(slog.NewJSONHandler(...))` makes the
  package's debug record testable. (We chose parameter injection over
  package-level `Logger` swap because the Python source has no notion
  of a per-call logger; the parameter lets us stay scoped.)
- **`SessionManager` interface.** The Python `set_session_manager(sm)`
  helper was duck-typed. The Go port makes the contract explicit: a
  `SessionManager` exposes a single `PostActivity(ctx, owner, role,
  content, category *string) error` method. The default implementation
  is a noop; callers can wire a real one for forward compatibility,
  but the shim will not call it.
- **Category resolution.** Explicit `LogOptions.Category` wins over
  the parsed legacy tag, matching the Python module's `*, category`
  keyword argument.

## Layout

```
go-src/assistant_log/
  go.mod                            # module github.com/odysseus/assistant_log, go 1.22
  README.md                         # this file
  pkg/assistantlog/
    logger.go                       # LogOptions, Result, SessionManager,
                                    # noopSessionManager, SetSessionManager,
                                    # LogToAssistant
    legacy_tag.go                   # LegacyTagRE + ParseLegacyTag
    helpers_test.go                 # table-driven coverage + slog capture
  cmd/assistantlog-demo/
    main.go                         # --help / --list-tests / --owner /
                                    # --content / --role / --category CLI
```

## Demo CLI

```bash
cd go-src/assistant_log

go run ./cmd/assistantlog-demo --help
go run ./cmd/assistantlog-demo --list-tests
go run ./cmd/assistantlog-demo
# logged=false reason="legacy no-op" category="Download" \
# owner="demo-owner" role="assistant"

go run ./cmd/assistantlog-demo \
    --owner alice \
    --content "**[Email]** inbox sync complete" \
    --category Manual
# logged=false reason="legacy no-op" category="Manual" owner="alice" role="assistant"
```

`--help` and `--list-tests` exit 0 on stdout per the wave-9 standing
rule. `--list-tests` prints a hard-coded list that mirrors `go test
-list .*` exactly (verified at port time).

## Running tests

```bash
cd go-src/assistant_log
go build ./...
go test -race ./...
go vet ./...
```

Tests use only stdlib (`bytes`, `context`, `log/slog`, `strings`,
`sync`, `testing`). The package has no external dependencies.

## Out of scope

- **Real activity routing.** The Python module does not write anywhere
  anymore; the Go port matches that. A future port that needs
  activity writes should consume Tasks / notifications rather than
  reviving this shim.
- **Async / queue semantics.** The Python module's `log_to_assistant`
  is synchronous and the Go port is the same.
- **Cross-language session-manager compatibility.** The Python
  `set_session_manager` was duck-typed; the Go port defines a
  forward-looking `SessionManager` interface but does not import or
  wrap any concrete Python implementation.