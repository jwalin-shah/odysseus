# agent_runs

A Go port of `src/agent_runs.py`: a detached agent-run manager for SSE streams.

## What it does

Keeps an agent/chat stream running server-side after the SSE client
disconnects (tab close, navigate away, refresh). A background goroutine drains
a `Source` into a per-session replay buffer; SSE clients `Subscribe` to that
buffer (replay everything so far, then live).

Reconnecting mid-run replays the buffer and continues streaming from the
live position. Closing the SSE only drops the subscriber — the drain keeps
going. In-memory only; does not survive a server restart.

## Layout

```
go-src/agent_runs/
├── go.mod
├── README.md
├── cmd/agentruns/main.go        # demo CLI: start, simulate events, subscribe, print, stop
└── pkg/agentruns/
    ├── manager.go               # Manager, Run, Subscription, IsActive/GetStatus/Start/Subscribe/Stop
    └── manager_test.go          # full coverage including -race
```

## Public surface

```go
type Source interface {
    Next(ctx context.Context, sink func(ev string)) error
}

type Manager struct { /* ... */ }
func New() *Manager
func NewWithGrace(evictGrace time.Duration) *Manager

func (m *Manager) Start(sessionID string, src Source) *Run
func (m *Manager) Stop(sessionID string) bool
func (m *Manager) IsActive(sessionID string) bool
func (m *Manager) GetStatus(sessionID string) (Status, bool)
func (m *Manager) Subscribe(ctx context.Context, sessionID string) (*Subscription, error)

type Subscription struct { /* ... */ }
func (s *Subscription) Next(ctx context.Context) (Event, bool)
func (s *Subscription) Close()
```

Status values: `running`, `done`, `error`, `stopped`.

## Port notes

- **Concurrency**: a single `sync.Mutex` guards the `Manager.runs` map; each
  `Run` has its own mutex for buffer / subscribers / status. Drain is a
  goroutine, not an asyncio task. `Stop` and `Start` cancel via
  `context.CancelFunc`.
- **Eviction**: `time.AfterFunc` is used in place of `asyncio.sleep` inside an
  `asyncio.create_task`. Eviction is cancelled on `Subscribe` and re-armed on
  the last subscriber leaving a finished run.
- **Replay-stripping**: `Subscription.Next` skips events whose `Seq` is below
  the high-water mark already replayed from the buffer.
- **Double-send cancellation**: `Start` cancels the previous drain's
  context and the new drain waits on the old drain's `done` channel before
  publishing — same semantics as Python's `await asyncio.wait({prev_task})`.

## Test approach

Tests use a configurable grace period (`NewWithGrace`, default 50ms in tests,
180s in production) so eviction paths can be observed without multi-second
sleeps. `time.AfterFunc` cancellation is the primary mechanism; tight polling
loops with short `time.Sleep` windows confirm transitions. The
`TestConcurrentSubscribersSafe` test exercises the race detector under
concurrent Start/Subscribe/Stop.

Run:

```
go build ./...
go test -race ./...
```