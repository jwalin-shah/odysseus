# runtime_paths (Go port)

Go port of `src/runtime_paths.py`. The Python module is a 29-line helper
that resolves two paths the rest of the app uses everywhere:

- **App root** — the directory the running process treats as its own
  top-level workspace. In source runs this is the repo root; in frozen
  PyInstaller builds it is the bundle content root (`sys._MEIPASS`) so
  bundled assets (`static/`, `scripts/`, `data/`) stay co-located with
  the executable payload.
- **Default data directory** — where persistent state (SQLite DB,
  uploads, sessions, etc.) is written. In source runs this is
  `<app_root>/data`; in frozen builds it is `~/.odysseus/data` so
  persistent state survives across bundle replacements.

The Go port captures the same behaviour behind a small, testable surface
using only stdlib (`os`, `path/filepath`, `os/exec`).

## Scope

This package re-implements exactly the two functions in the Python
module. It does NOT re-implement PyInstaller; instead it offers an
`Environment` interface that callers can populate to describe the
"frozen" condition (bundle dir, executable path) so tests and
alternative launchers (Bazel, `go run`, packaged binaries, containers)
can drive the resolver deterministically.

The port covers:

- **`GetAppRoot(env)`** — equivalent of `get_app_root()`. Honors a
  caller-supplied `Environment`. Default `Environment` reads from
  Go's `os.Args[0]` (the running executable) the same way Python
  reads `sys.executable`.
- **`GetDefaultDataDir(env)`** — equivalent of `get_default_data_dir()`.
  Joins the frozen-bundle user home with `.odysseus/data` when frozen,
  else joins `GetAppRoot` with `data`.
- **`FrozenProbe`** — tiny helper that exec's `uname` (or
  `/System/Library/CoreServices/SystemVersion.plist` on Darwin) to
  decide whether the binary looks like it was packaged by an external
  bundler. This is intentionally separate from the resolver because
  it is the only piece that touches `os/exec`; tests can swap it for a
  stub via `Environment.Frozen`.

## Layout

```
go-src/runtime_paths/
  go.mod                       # module github.com/odysseus/runtime_paths
  go.sum
  README.md
  cmd/runtimepaths-demo/main.go  # small CLI demo: --print exercises the surface
  pkg/runtimepaths/
    types.go                   # Environment struct, FrozenInfo
    paths.go                   # GetAppRoot, GetDefaultDataDir
    helpers.go                 # internal helpers (normalize, expandUser)
    helpers_unix.go            # *nix home expansion (HOME)
    helpers_windows.go         # Windows home expansion (USERPROFILE)
    paths_test.go              # table-driven tests
```

## Public API

```go
type Environment struct {
    Frozen    bool        // true when running from a frozen bundle
    BundleDir string      // frozen bundle root (e.g. PyInstaller's _MEIPASS)
    ExecPath  string      // os.Args[0] equivalent (sys.executable)
    HomeDir   string      // user home (os.Getenv("HOME") / USERPROFILE)
}

func GetAppRoot(env Environment) string
func GetDefaultDataDir(env Environment) string
```

Both functions tolerate zero-value `Environment`. They never panic; an
empty `ExecPath` falls back to `os.Getwd` and an empty `HomeDir`
falls back to `os.UserHomeDir`.

## Environment variable handling

- **Source runs** (`Environment.Frozen == false`): the app root is the
  parent of the parent of the file containing this package's source.
  In a `go build`/`go run` invocation we mirror that by climbing
  `os.Getwd` upward until we find a `go.mod`. That matches the
  Python behaviour (the parent of the parent of `__file__`).
- **Frozen runs** (`Environment.Frozen == true`): `BundleDir` is
  preferred; if empty, we fall back to `filepath.Dir(ExecPath)`.
- **Home expansion** uses `HOME` on Unix and `USERPROFILE` on
  Windows. When both are empty we call `os.UserHomeDir()` once and
  cache the result on the `Environment` so repeated calls stay
  deterministic.

## Usage

```go
import contextrp "github.com/odysseus/runtime_paths/pkg/runtimepaths"

env := contextrp.Environment{ExecPath: os.Args[0], HomeDir: os.Getenv("HOME")}
root := contextrp.GetAppRoot(env)
data := contextrp.GetDefaultDataDir(env)
```

## Demo CLI

```bash
cd go-src/runtime_paths
go run ./cmd/runtimepaths-demo --print
```

The CLI prints both `AppRoot` and `DefaultDataDir` for the current
process so a reviewer can eyeball the resolution.

## Port notes

- **`sys.frozen` analogue.** Go has no built-in "frozen" flag; we use
  the explicit `Environment.Frozen bool`. Tests pass `Frozen: true`
  with a custom `BundleDir`; production wiring should set this when
  the binary is packaged by an external bundler.
- **`sys._MEIPASS` analogue.** `Environment.BundleDir` mirrors
  `_MEIPASS` 1:1 — when frozen, `BundleDir` is the bundle content
  root.
- **`__file__` analogue.** We don't have a direct equivalent of
  `__file__` in compiled binaries. The resolver climbs `os.Getwd`
  looking for a `go.mod` (the closest Go analogue to the Python
  module's location). When `Environment.ExecPath` is supplied
  (typical for production binaries), we use `filepath.Dir(ExecPath)`
  to match the Python module's `os.path.dirname(os.path.abspath(__file__))`
  fallback.
- **Frozen fallback path.** When `Frozen == true` but `BundleDir`
  is empty, we fall back to `filepath.Dir(ExecPath)` — same as the
  Python `getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))`
  expression.
- **No external dependencies.** stdlib only.

## Tests

```bash
cd go-src/runtime_paths
go test ./...
```

Tests are table-driven and cover: env var set, env var unset, default
fallback, frozen vs. unfrozen, nested app roots, empty `ExecPath`,
empty `HomeDir`, and `t.TempDir()`-backed filesystem resolution.
