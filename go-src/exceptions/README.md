# exceptions (Go port)

Go port of [`src/exceptions.py`](../../src/exceptions.py). The Python module
defines four custom exception classes — `SessionNotFoundError`,
`InvalidFileUploadError`, `LLMServiceError`, `WebSearchError` — that share a
common base (`Exception`) but carry different structured fields (session id,
filename, endpoint, query). The Go port translates that hierarchy to a single
typed `*odyexceptions.Error` struct with a `Code` discriminator, plus per-class
constructors and package-level sentinel errors that match the way Python
callers raise and catch by class.

## Layout

```
go-src/exceptions/
  go.mod                # module github.com/odysseus/exceptions, go 1.22
  go.sum                # empty — stdlib only
  README.md             # this file
  pkg/odyexceptions/
    types.go            # Code enum + Error struct + Error()/Unwrap()/Is()/As()
    helpers.go          # Err* sentinels, New* constructors, Wrap, AsError
    internal.go         # errors.As shim (keeps helpers.go readable)
    exceptions_test.go  # construction, errors.Is/As, Wrap chains, formatting
  cmd/odyexceptions-demo/
    main.go             # demo CLI: constructs each type and walks Is/As
```

## Mapping (Python → Go)

| Python (src/exceptions.py)            | Go (odyexceptions)                              |
| ------------------------------------- | ----------------------------------------------- |
| `SessionNotFoundError(session_id)`    | `NewSessionNotFound(id)`                        |
| `InvalidFileUploadError(msg, name)`   | `NewInvalidFileUpload(msg, name)`               |
| `LLMServiceError(msg, endpoint)`      | `NewLLMService(msg, endpoint)`                  |
| `WebSearchError(msg, query)`          | `NewWebSearch(msg, query)`                      |
| `raise Foo(...)`                      | `return NewFoo(...)` (functions return `error`) |
| `except Foo:` / `except Foo as e`     | `if errors.Is(err, ErrFoo) { ... }`             |
| `except BaseException` / typed cast   | `errors.As(err, &target)`                       |
| chained `raise Foo(...) from exc`     | `Wrap(exc, Code, msg)`                          |

The Python instance attributes (`session_id`, `filename`, `endpoint`,
`query`) become fields on the Go `*Error` struct. Callers that just want the
typed hierarchy can ignore them — the `Code` is enough for `errors.Is`.

## Why a single struct

In Python each class gets its own type so callers can `except Foo` directly.
Go's error hierarchy is interface-based, but the cleanest translation that
preserves the structured fields is one concrete struct with a `Code`
discriminator:

- It satisfies `error` (so it composes with anything that takes `error`).
- It has `Unwrap` so `errors.Is/As` walk across `Wrap` chains.
- Per-class constructors (`NewSessionNotFound`, ...) set both the `Code` and
  the matching field, so callers writing `NewLLMService("boom", url)` get the
  same shape they would have gotten from `LLMServiceError("boom", url)` in
  Python.

`Code` is `int` because the values are only ever compared with the named
constants — the integers themselves carry no meaning outside the package.

## Public API

```go
import (
    "errors"

    contextodexc "github.com/odysseus/exceptions/pkg/odyexceptions"
)

// --- Sentinels for errors.Is matching ---
contextodexc.ErrSessionNotFound
contextodexc.ErrInvalidFileUpload
contextodexc.ErrLLMService
contextodexc.ErrWebSearch

// --- Codes (use these when wrapping raw errors or building a generic Error) ---
contextodexc.CodeUnknown
contextodexc.CodeSessionNotFound
contextodexc.CodeInvalidFileUpload
contextodexc.CodeLLMService
contextodexc.CodeWebSearch

// --- Per-class constructors ---
err := contextodexc.NewSessionNotFound("abc123")        // SessionNotFoundError("abc123")
err := contextodexc.NewInvalidFileUpload("too large", "big.csv")
err := contextodexc.NewLLMService("503", "https://api/v1")
err := contextodexc.NewWebSearch("dns", "go errors")

// --- Generic constructors ---
err := contextodexc.NewError(contextodexc.CodeLLMService, "raw")
err := contextodexc.Wrap(stdlibErr, contextodexc.CodeLLMService, "outer")

// --- errors.Is / errors.As ---
if errors.Is(err, contextodexc.ErrLLMService) { ... }

var t *contextodexc.Error
if errors.As(err, &t) {
    fmt.Println(t.Endpoint) // structured field survives the wrap
}

// --- AsError convenience ---
if e := contextodexc.AsError(err); e != nil {
    fmt.Println(e.Code)
}
```

## Wrap / Unwrap semantics

`Wrap(err, code, msg)` returns a fresh `*Error` whose `Cause` is `err`. The
returned error carries the requested `Code`, so `errors.Is` against the
matching sentinel still succeeds even when the cause was a stdlib error like
`os.ErrNotExist`.

`(*Error).Unwrap()` returns the `Cause` field so `errors.Unwrap` /
`errors.Is` / `errors.As` walk the chain the same way `raise X from Y` does
in Python.

`(*Error).Error()` renders as `"<code>: <message>"`. When a `Cause` is set,
its message is appended with `": <cause>"` so nested errors stay inspectable
in logs.

## Running tests

```bash
cd go-src/exceptions
go build ./...
go test ./...
```

Tests use only the stdlib `testing` and `errors` packages — no fixtures, no
network, no temp files.

## Demo CLI

```bash
cd go-src/exceptions
go run ./cmd/odyexceptions-demo
```

The CLI prints one line per typed error, walks a representative `Wrap` chain,
and confirms `errors.Is` matches the right sentinel at the top of the chain.
It exits 0 on success.

## When to use which class

- **SessionNotFoundError** — caller asked for a session that does not exist.
  The `session_id` is the only structured field.
- **InvalidFileUploadError** — uploaded file failed validation (size, MIME,
  extension, content sniff). `message` carries the reason, `filename` the
  uploaded file's basename.
- **LLMServiceError** — anything wrong on the path to/from the LLM provider:
  timeouts, 4xx/5xx, JSON parse failures, rate limits. `endpoint` is the URL
  of the failing call so logs can attribute failures to the right provider.
- **WebSearchError** — search provider is unavailable, returned an error, or
  the query was rejected. `query` is the search string so logs can correlate
  errors with user intent.

If a failure doesn't fit any of these four, build it with `NewError(code,
msg)` or wrap a stdlib error with `Wrap` — the rest of the codebase can still
match it via `errors.As(err, &target)` and inspect `Code`.

## Port notes

- **Python `__init__` defaults** (`filename=None`, `endpoint=None`,
  `query=None`) map to Go's zero string `""`. Callers that need to
  distinguish "not set" from "set to empty string" should use the structured
  fields explicitly.
- **`super().__init__(message)`** in Python is implicit in Go: `*Error.Error()`
  prints the message plus code automatically.
- **`isinstance(exc, Foo)`** is `errors.As` (or `errors.Is` against the
  sentinel).
- **`raise Foo from cause`** is `Wrap(cause, code, msg)`. The cause is
  rendered at the tail of `Error()`.
- **No `traceback` in Go.** Stack traces come from `runtime.Callers` or a
  logger; `*Error` doesn't capture them itself. Production callers should log
  the error with `%+v` (or wrap with `fmt.Errorf("...: %w", err)`) so the
  surrounding context is preserved.