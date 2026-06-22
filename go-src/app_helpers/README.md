# app_helpers (Go port)

Go port of `src/app_helpers.py` — the four tiny helpers used by routes
and services throughout the app:

```python
def read_if_exists(path: str) -> str:
    """Read file if it exists, return empty string otherwise."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""

def file_to_data_url(path: str, mime: str) -> str:
    """Convert file to data URL."""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"

def abs_join(base_dir: str, rel: str) -> str:
    """Join paths and return absolute path."""
    return os.path.abspath(os.path.join(base_dir, rel))

def inside_base_dir(base_dir: str, path: str) -> bool:
    """Check if path is inside base directory."""
    if not isinstance(base_dir, str) or not isinstance(path, str):
        return False
    base = os.path.realpath(base_dir)
    p = os.path.realpath(path)
    try:
        return os.path.commonpath([base, p]) == base
    except Exception:
        return False
```

The Go port keeps all four contracts and adds:

- `ReadIfExists` returns `""` (not an error) for missing/unreadable files,
  mirroring the broad `except Exception` in Python.
- `FileToDataURL` refuses empty `path` / `mime` — the Python source
  would happily emit `data:;base64,...` which is a footgun.
- `InsideBaseDir` uses `filepath.EvalSymlinks` so symlink games cannot
  smuggle a path out of `base_dir` — the Python source uses
  `os.path.realpath` for the same reason.
- `AbsJoin` is `filepath.Abs(filepath.Join(...))` — does **not** resolve
  symlinks (use `InsideBaseDir` for that). This matches the Python
  behavior, which uses `os.path.abspath` rather than `os.path.realpath`.

## Public API

```go
func ReadIfExists(path string) string
func FileToDataURL(path, mime string) (string, error)
func AbsJoin(base, rel string) string
func InsideBaseDir(base, path string) bool
```

## Why `InsideBaseDir` uses `EvalSymlinks` and not `Abs`

`filepath.Abs` calls `os.Getwd` to make a path absolute, but it does
**not** follow symlinks. `filepath.EvalSymlinks` does. A symlink that
points outside `base_dir` would pass a string-based check (e.g.
`strings.HasPrefix`) while pointing at an attacker-controlled
location. `EvalSymlinks` resolves the link before the comparison.

## Layout

```
app_helpers/
├── go.mod
├── README.md
├── pkg/apphelpers/
│   ├── helpers.go        # ReadIfExists, FileToDataURL, AbsJoin, InsideBaseDir
│   └── helpers_test.go   # table-driven coverage + symlink / traversal tests
└── cmd/apphelpers-demo/
    └── main.go           # walks all four helpers against a tempdir
```

## Demo

```
go run ./cmd/apphelpers-demo
```

Output (paths will vary; abbreviated):

```
== apphelpers demo ==

[read_if_exists]
  /var/folders/.../T/notes.txt -> "hello world"
  /var/folders/.../T/nope.txt -> ""

[file_to_data_url]
  /var/folders/.../T/notes.txt
  -> "data:text/plain;base64,aGVsbG8gd29ybGQ="

[abs_join]
  "/var/folders/.../T/001" + "sub/file.txt" -> "/var/folders/.../T/001/sub/file.txt"

[inside_base_dir]
  base="/var/folders/.../T/001"
  nested ("/var/folders/.../T/001/sub")        inside=true (want true)
  sibling ("/var/folders/.../T/sibling-outside") inside=false (want false)
  missing                                   inside=false (want false)
```
