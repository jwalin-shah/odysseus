# rate_limiter (Go port)

Go port of [`src/rate_limiter.py`](../../src/rate_limiter.py). The Python
module is a single class, `RateLimiter`, that implements a sliding-window
in-memory rate limiter keyed by an arbitrary string (in the Odysseus server
this is the request IP). The Go port keeps the same public shape — one
constructor, one `Allow` check, identical semantics — and adds a tiny
optional `Stats` surface for observability that mirrors the Python's
internal log map.

The original `check()` is renamed `Allow()` to follow Go-idiomatic naming
(`http.ResponseWriter.WriteHeader`, `bufio.Reader.Read`, etc.). Behavior is
preserved exactly:

- A key is admitted while its trailing-window count is **strictly less**
  than `MaxRequests`. The `max_requests`-th request within the window is
  rejected.
- The window slides over `time.Now()` monotonic timestamps; entries older
  than `Window` are evicted on every check (lazy GC).
- A periodic background sweep runs every `max(2 * Window, 120s)` and
  removes keys whose newest entry is already past the cutoff — same as the
  Python `_maybe_cleanup`.
- All mutations are guarded by a single `sync.Mutex`, matching the Python
  `threading.Lock`. The Go race detector is the proof of correctness under
  concurrent callers (validated in `pkg/ratelimiter/ratelimiter_test.go`).

## Layout

```
go-src/rate_limiter/
  go.mod                       # module github.com/odysseus/rate_limiter, go 1.22
  README.md                    # this file
  pkg/ratelimiter/
    ratelimiter.go             # public API: NewLimiter, *Limiter.Allow, Stats, Reset
    ratelimiter_test.go        # table-driven tests + race smoke + cleanup behavior
  cmd/ratelimiter-demo/
    main.go                    # --help flag + smoke-test CLI
```

## Mapping (Python → Go)

| Python (src/rate_limiter.py)            | Go (github.com/odysseus/rate_limiter/pkg/ratelimiter) |
| --------------------------------------- | ---------------------------------------------------- |
| `RateLimiter(max_requests, window_seconds)` | `NewLimiter(maxRequests, window time.Duration)`  |
| `limiter.check(key)` returning `bool`   | `limiter.Allow(key)` returning `bool`                |
| `self._log` (Dict[str, List[float]])    | internal `map[string]*keyState` (private)            |
| `self._lock` (threading.Lock)           | `sync.Mutex`                                         |
| `time.monotonic()`                      | `time.Now()` (Go's monotonic clock since `go 1.9`)   |
| `self._cleanup_interval` (2× window, min 120s) | computed once in `NewLimiter`, same formula   |
| `self._last_cleanup`                    | `time.Time` field on `*Limiter`                      |
| `del self._log[k]` (stale key eviction) | `delete(lm.log, k)`                                  |

The Python class itself is a single unit; the Go port keeps it that way
rather than splitting into a manager + per-key state struct. The only
helper struct (`keyState`) is unexported and exists purely so the entry
list can grow without re-allocating on every check.

## Public API

```go
import (
    "time"

    rl "github.com/odysseus/rate_limiter/pkg/ratelimiter"
)

limiter := rl.NewLimiter(5, 60*time.Second)

if !limiter.Allow("203.0.113.5") {
    // 429 Too Many Requests
}

// Stats lets middleware log how big the table is. Keys are not exposed
// because the IP table is sensitive in production.
fmt.Println(limiter.Stats()) // {Keys: 17, MaxRequests: 5, Window: 1m0s}

// Wipe all state. Useful in tests and on admin "reset my tenant".
limiter.Reset()
```

### Why `time.Duration`, not `int` seconds

The Python module uses `window_seconds: int`; the Go port uses
`time.Duration`. That is the idiomatic representation in Go — callers don't
have to multiply by `time.Second` themselves, and the same value works in
`time.AfterFunc` / `time.NewTicker` if the port later adds a background
sweeper goroutine. The conversion is trivial:

```go
limiter := rl.NewLimiter(5, 60*time.Second)             // 5 req / 1 minute
limiter := rl.NewLimiter(100, 2500*time.Millisecond)    // 100 req / 2.5 s
```

### Concurrency

`*Limiter.Allow` is safe for concurrent use. The internal map and timestamp
list are guarded by a single `sync.Mutex`; the implementation deliberately
avoids `sync.RWMutex` because every `Allow` is a write (it appends a
timestamp when the key is admitted). `go test -race ./...` exercises the
table under concurrent callers — see `TestAllowConcurrent` and
`TestAllowConcurrentStaleEviction`.

### Cleanup behavior

The Python module runs `_maybe_cleanup(now)` on **every** `check`, but only
acts when the elapsed interval exceeds `_cleanup_interval`. The Go port
keeps that exactly: the elapsed check is a `time.Since(lm.lastCleanup)`
comparison, and the purge only runs at or past the interval. Tests pin
this with a stub clock (`clockFn`) so we can advance time deterministically
without sleeping.

`keyState.entries` is rebuilt in place on each check (Python's
`[t for t in timestamps if t > cutoff]`); the Go port does the same with
`append([]float64(nil), keep...)` so we never mutate a slice that another
goroutine might be reading.

### What's NOT ported

- **No `HTTPException` integration.** The Python docstring shows
  `raise HTTPException(429, ...)` as an example. The Go port returns `bool`
  so the caller (HTTP middleware) decides how to translate to a status
  code — exactly like the Python `check()` return value. Wiring the
  response is out of scope for this module.
- **No distributed / Redis-backed variant.** The Python module is purely
  in-memory; the Go port is the same. If the server later needs to share
  state across pods, that belongs in a separate module that wraps this one.

## Running tests

```bash
cd go-src/rate_limiter
go build ./...
go test -race ./...
go vet ./...
```

The test file is stdlib-only (`testing`, `sync`, `time`).

## Demo CLI

```bash
cd go-src/rate_limiter
go run ./cmd/ratelimiter-demo --help
go run ./cmd/ratelimiter-demo --key 203.0.113.5 --max 5 --window 1m
```

The CLI runs the same allow/reject logic against a fresh limiter and prints
a one-line summary per request. Exit 0 when the request is admitted, exit
1 when it is rate-limited. `--key` may be passed multiple times to simulate
a burst:

```bash
for i in 1 2 3 4 5 6; do
  go run ./cmd/ratelimiter-demo --key demo --max 5 --window 1m || break
done
```
