# cookbook_serve_lifecycle (Go port)

Go port of [`src/cookbook_serve_lifecycle.py`](../../src/cookbook_serve_lifecycle.py).
The Python module is a small asyncio loop that ticks every 60 seconds and
kills tmux sessions for scheduler-launched cookbook serves whose
`_scheduledStopAtMs` window has expired, then drops the auto-registered
model endpoint so the picker doesn't keep pointing at a dead server. The
Go port keeps the same semantics but splits the work into focused,
testable pieces: a pure state-file parser, a pure URL/command builder, an
injectable `Client` interface, and a `Lifecycle` struct that drives the
loop.

## What this package does

`cookbookserve.Lifecycle.Tick(ctx)` is a single iteration of the Python
loop: read the state JSON, find tasks whose stop window has passed, kill
the tmux session, drop the endpoint (for `type=="serve"` tasks), then
re-read the state file and patch only the successfully-stopped entries
before writing atomically. `Lifecycle.Run(ctx)` wraps `Tick` in a
context-aware forever loop that mirrors the Python `asyncio.sleep(60)`
cadence.

The package has **zero external dependencies** — stdlib only — and no
runtime coupling to Flask, httpx, or the Odysseus DB. Callers inject a
`cookbookserve.Client` (the package ships a `*HTTPClient` that talks to
the same internal API the Python module calls via httpx) and the
package handles everything else.

## Public API

```go
import (
    "github.com/jwalin-shah/odysseus/cookbook_serve_lifecycle/pkg/cookbookserve"
)

lc := cookbookserve.NewLifecycle()
lc.StateFilePath = "/var/lib/cookbook/state.json"
lc.Client = cookbookserve.NewHTTPClient()
lc.Logger = log.Default()

// Run a single tick (mirrors the Python _tick function).
if err := lc.Tick(ctx); err != nil { ... }

// Or drive the forever loop, identical to cookbook_serve_lifecycle_loop().
err := lc.Run(ctx)
```

## Mapping (Python → Go)

| Python (src/cookbook_serve_lifecycle.py)            | Go (github.com/jwalin-shah/odysseus/cookbook_serve_lifecycle/pkg/cookbookserve) |
| --------------------------------------- | ---------------------------------------------------- |
| `_tick()`                          | `(*Lifecycle) Tick(ctx)`                       |
| `cookbook_serve_lifecycle_loop()`   | `(*Lifecycle) Run(ctx)`                        |
| `_delete_endpoint_for_task(task)`   | `(*Lifecycle) StopTask(ctx, task)` (kill + best-effort delete) |
| `_stop_serve(sid, host, port)`      | `BuildKillCommand(...)` + `Client.ExecCommand(...)` |
| `(remote, port, cmd) -> base_url`   | `HostFromRemote` + `ExtractPortFromCommand` + `BuildBaseURL` |
| httpx call to `/api/model-endpoints`| `(*HTTPClient) ListEndpoints` / `DeleteEndpoint` |
| httpx call to `/api/shell/exec`     | `(*HTTPClient) ExecCommand`                    |
| `logger.info(...)`                 | `Lifecycle.Logger.Printf(...)` (defaults to `io.Discard`) |
| `core.atomic_io.atomic_write_json`  | `WriteStateFileAtomic(path, *State)`           |

The Python instance attributes (`sessionId`, `_scheduledStopAtMs`,
`payload._cmd`, etc.) become fields on `cookbookserve.Task`. The Go
`Task.Extra` map preserves any keys the Python writer adds that aren't
modelled here, so a round-trip through `ReadStateFile` +
`WriteStateFileAtomic` does not silently drop them.

## Layout

```
cookbook_serve_lifecycle/
  go.mod                  # module github.com/jwalin-shah/odysseus/cookbook_serve_lifecycle, go 1.22
  README.md               # this file
  pkg/cookbookserve/
    lifecycle.go          # Lifecycle struct, NewLifecycle, Run (forever loop)
    tick.go               # Tick, StopTask, FindTasksToStop, deleteEndpointForTask
    state.go              # Task, State, ReadStateFile, WriteStateFileAtomic
    client.go             # Client interface, Endpoint, ExecResult, HTTPClient, URL/cmd helpers
    errors.go             # exported sentinel errors
    cookbookserve_test.go # table-driven coverage of every exported function
  cmd/cookbooklifecycle-demo/
    main.go               # demo CLI: single tick by default, -loop for the forever loop
```

## Why a `Client` interface

The Python module talks directly to httpx. The Go port accepts any
`cookbookserve.Client` so tests can inject a fake (see `fakeClient` in
`cookbookserve_test.go`) and exercise `Tick`/`StopTask` without a
network. The production wiring (`*HTTPClient`) uses stdlib `net/http`
against `InternalAPIBase()` (env `ODY_INTERNAL_API_BASE`, default
`http://127.0.0.1:8000`) with the same internal-tool token the Python
module reads from `core.middleware`.

## What's NOT ported

- **The Flask app registration line** in `app.py` that registers
  `cookbook_serve_lifecycle_loop()` as a startup task. The Go port is a
  callable package + a standalone CLI; supervisors wire `Lifecycle.Run`
  into their own boot path. Use `cmd/cookbooklifecycle-demo -loop` to
  run the forever loop standalone.
- **`COOKBOOK_STATE_FILE`** — the Python module imports the path from
  `src.constants`. The Go port takes the path from `Lifecycle.StateFilePath`
  and reads `ODY_COOKBOOK_STATE_FILE` as the CLI default. There is no
  `src/constants.py` import in Go.
- **`core.middleware.INTERNAL_TOOL_HEADER` / `INTERNAL_TOOL_TOKEN`** —
  the Go port defines its own `cookbookserve.HeaderName` and
  `cookbookserve.Token()` (env `ODY_INTERNAL_TOOL_TOKEN`, default
  `"dev"`). When this module is wired into a server that already
  configures those constants, set `HTTPClient.Headers` explicitly.
- **The Flask `internal_api_base()`** helper — replaced with
  `cookbookserve.APIBase()` (env `ODY_INTERNAL_API_BASE`).
- **The asyncio scheduling** — Go uses `time.Ticker` + `context.Context`
  cancellation instead of an `asyncio.sleep(60)` loop. Operators
  signal shutdown with SIGINT/SIGTERM (the CLI does this for you).

## Public API surface

```go
// Types
type Lifecycle struct{ ... }
type Client interface { ... }
type HTTPClient struct{ ... }
type Endpoint struct{ ... }
type ExecResult struct{ ... }
type Task struct{ ... }
type State struct{ ... }

// Constructors / package-level helpers
func NewLifecycle() *Lifecycle
func NewHTTPClient() *HTTPClient
func Token() string
func APIBase() string
func InternalHeaders() map[string]string

// Loop / tick
func (l *Lifecycle) Run(ctx context.Context) error
func (l *Lifecycle) Tick(ctx context.Context) error
func (l *Lifecycle) StopTask(ctx context.Context, task Task) error

// State file
func ReadStateFile(path string) (*State, error)
func WriteStateFileAtomic(path string, s *State) error
func FindTasksToStop(s *State, nowMs int64) []Task

// URL / command construction
func BuildKillCommand(sessionID, remoteHost, sshPort string) string
func BuildBaseURL(host string, port int) string
func HostFromRemote(remote string) string
func ExtractPortFromCommand(cmd string, defaultPort int) int
func StopSucceededFromExec(res ExecResult) bool

// Errors (sentinels for errors.Is)
var (
    ErrNilLifecycle
    ErrNilClient
    ErrMissingSessionID
    ErrKillFailed
    ErrEmptyStatePath
)
```

## Running tests

```bash
cd go-src/cookbook_serve_lifecycle
go build ./...
go test -race ./...
go vet ./...
```

The test file is stdlib-only (`testing`, `context`, `encoding/json`,
`errors`, `os`, `path/filepath`, `reflect`, `sync`).

## Demo CLI

```bash
cd go-src/cookbook_serve_lifecycle
go run ./cmd/cookbooklifecycle-demo -state /path/to/cookbook_state.json
```

Default behavior runs a single tick (matches Python `_tick()`) and
prints `cookbooklifecycle-demo: tick complete (stopped=N)` where `N` is
the count of expired tasks observed at the start of the tick. The
`-loop` flag drives the forever loop (`Run`) with the default 60s
tick / 20s initial sleep, mirroring `cookbook_serve_lifecycle_loop()`.

## Design choices

- **Single `State.Extra` field** preserves any non-`tasks` keys the
  Python writer adds so concurrent UI syncs that mutate sibling keys
  survive a `Tick` write. This is how `core.atomic_io.atomic_write_json`
  behaves too — round-tripping the state file is lossless.
- **`Tick` re-reads the state file** before writing, matching the
  Python `try: fresh = json.loads(...)` pattern. Without it a
  concurrent UI write (task add, config edit) would be silently
  overwritten.
- **Endpoint delete is best-effort** — `StopTask` logs the error but
  does not propagate it, matching the Python `_delete_endpoint_for_task`
  except-block. The kill succeeded; the cleanup is a follow-up.
- **`HTTPClient` has no retries** — same as the Python httpx calls.
  Network blips surface as errors that the lifecycle logs and
  continues past.
- **No `httpx` dependency** — stdlib `net/http` only. The transport
  surface is small enough that wrapping it in an interface gives tests
  full control without losing production fidelity.