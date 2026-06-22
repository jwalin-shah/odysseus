# readiness (Go port)

Go port of `src/readiness.py` — the local-instance readiness / integrity
self-check served by `GET /api/ready` (and used as an orchestrator
readiness probe). The Python source runs three checks:

1. `database` — open a SQLAlchemy engine and execute `SELECT 1`.
2. `data_dir` — `os.makedirs(DATA_DIR, exist_ok=True)`, write a probe
   file, remove it.
3. `local_first` — informational; storage stays on this host iff the
   database URL starts with `sqlite`, contains `localhost`, or
   contains `127.0.0.1`.

The Go port keeps the same shape and report, with one deliberate
change: the Go module does not depend on a SQL driver (no
`database/sql` import at all). Instead, the DB check is plugged in via
a small `Probe` interface so callers can wire in their own pool
health check.

## Public API

```go
const AppVersion = "1.0.0"

type Probe interface { Ping(ctx context.Context) error }
type ProbeFunc func(ctx context.Context) error

type Options struct {
    DataDir       string
    DatabaseURL   string
    Version       string
    DatabaseProbe Probe
}

type Report struct {
    Ready      bool                   `json:"ready"`
    Version    string                 `json:"version"`
    Checks     map[string]CheckResult `json:"checks"`
    Timestamp  string                 `json:"timestamp"` // ISO-8601 UTC
    LocalFirst bool                   `json:"local_first"`
}

type CheckResult struct {
    OK    bool   `json:"ok"`
    Error string `json:"error,omitempty"`
    Path  string `json:"path,omitempty"`
    Local *bool  `json:"local,omitempty"`
}

func Check(ctx context.Context, opts Options) (*Report, error)
func IsLocalFirst(databaseURL string) bool
```

## Why a `Probe` interface

`src/readiness.py` uses SQLAlchemy. The Go port cannot — the odysseus
Go ports are stdlib-only by convention, and the readiness module should
not pull in a `database/sql` driver just to ping. Exposing a
single-method interface means the host process owns its pool and the
readiness check is pure-testable with a tiny stub.

When `DatabaseProbe == nil`, the `database` check is recorded as
`{"ok": false, "error": "no probe configured"}` — this mirrors the
"no engine configured" failure mode of the Python source.

## Why `Version` is on `Options`

`src/readiness.py` imports `APP_VERSION` from `core.constants`. The Go
port is self-contained: callers pass the version through `Options.Version`
each call. This keeps the port free of cross-module Go dependencies and
matches the wave9 convention of injecting configuration through a struct
rather than globals.

## Contracts preserved

- `ready` is `true` only when **every** check is `ok`. The
  `local_first` check is informational and is always recorded as
  `ok: true` (matching the Python `checks["local_first"] = {"ok": True, "local": ...}`).
- `data_dir` auto-creates the directory if missing (mimicking
  `os.makedirs(..., exist_ok=True)`).
- `local_first` heuristic: sqlite-prefixed URLs, `localhost`,
  `127.0.0.1` are local; everything else is not.
- `timestamp` is ISO-8601 UTC (`time.Now().UTC().Format(time.RFC3339)`),
  matching `datetime.utcnow().isoformat()` to the second.
- The temp probe file uses a hex suffix (`.ready_probe_<16-hex>`),
  mirroring Python's `f".ready_probe_{uuid.uuid4().hex}"`.

## Layout

```
readiness/
├── go.mod
├── README.md
├── pkg/readiness/
│   ├── probe.go         # Probe interface, ProbeFunc
│   ├── report.go        # Options, Report, CheckResult, Check, IsLocalFirst
│   ├── probe_test.go    # probe file behaviour + ProbeFunc adapters
│   └── report_test.go   # DB / data_dir / local_first / overall-ready cases
└── cmd/readiness-demo/
    └── main.go          # CLI with --help / --list-tests / --data-dir / --database-url / --version
```

## Demo

```
go run ./cmd/readiness-demo --help
go run ./cmd/readiness-demo --list-tests
go run ./cmd/readiness-demo --data-dir /tmp
```

The CLI never opens a real database; the local_first detection is
purely string-based, so any URL string is a valid input.