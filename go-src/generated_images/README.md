# generated_images (Go port)

Go port of `src/generated_images.py` — the small helper that guards the
public file-serving endpoint over a directory of generated images. The
Python module exposes a regex, a directory constant, a header map, and
a single resolver:

```python
GENERATED_IMAGE_DIR = Path(GENERATED_IMAGES_DIR)
GENERATED_IMAGE_RE = re.compile(
    r"^[a-f0-9]{8,64}\.(png|jpg|jpeg|webp|gif|mp4|mov|webm|mkv|m4v)$"
)
GENERATED_IMAGE_HEADERS = {
    "Cache-Control": "public, max-age=31536000, immutable",
    "X-Content-Type-Options": "nosniff",
}

def resolve_generated_image_path(filename: str) -> Path:
    if not isinstance(filename, str) or not GENERATED_IMAGE_RE.fullmatch(filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    root = GENERATED_IMAGE_DIR.resolve()
    path = (GENERATED_IMAGE_DIR / filename).resolve()
    try:
        if os.path.commonpath([str(root), str(path)]) != str(root):
            raise ValueError
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid filename")
    if not path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    return path
```

The Go port keeps every contract and returns **typed errors**
(`*FilenameError`, `*NotFoundError`) instead of HTTPExceptions. Callers
translate the typed error to a status code at the HTTP edge — that keeps
this package free of any HTTP framework dependency, which is the same
separation of concerns `src/url_security.py` and `src/prompt_security.py`
follow.

## What this package does

- **Filename validation.** `Match(name)` is a 1:1 port of the Python
  regex. The compiled form is exposed as `filenameRe` (lowercase) but
  callers should use `Match` so the regex stays internal.
- **Header table.** `ImageHeaders` is the canonical
  `Cache-Control` + `X-Content-Type-Options` set served alongside
  generated images. Pinned to the literal values from the Python
  source so a refactor can't drift them.
- **Path resolution.** `Resolve(dir, filename)` runs every check the
  Python source runs: regex match → root containment → existence.
  Returns the absolute path on success.

## Public API

```go
var AllowedExtensions []string                 // ["png", "jpg", ...]
var HashPattern string                         // `^[a-f0-9]{8,64}$`
var ImageHeaders map[string]string             // canonical response headers

type FilenameError struct{ Filename string }
type NotFoundError  struct{ Filename string }

var ErrFilename = errors.New("invalid filename")
var ErrNotFound = errors.New("image not found")

func Match(name string) bool
func Resolve(dir, filename string) (string, error)

func IsFilename(err error) bool
func IsNotFound(err error) bool
func AsError(err error) error
```

## Why typed errors instead of HTTP codes

`src/generated_images.py` is wired into FastAPI's `HTTPException`, so
its errors already carry a status code. The Go port lives one layer
down — the HTTP handler is the caller's job. Returning typed errors
keeps this package free of `net/http` imports and lets non-HTTP callers
(replication jobs, batch exports, etc.) reuse the same resolver.

A typical handler translation:

```go
path, err := generatedimages.Resolve(dir, filename)
switch {
case err == nil:
    // serve path with ImageHeaders
case generatedimages.IsFilename(err):
    http.Error(w, "invalid filename", http.StatusBadRequest)
case generatedimages.IsNotFound(err):
    http.Error(w, "image not found", http.StatusNotFound)
default:
    http.Error(w, "internal error", http.StatusInternalServerError)
}
```

## Path-traversal guard

`Resolve` uses `filepath.EvalSymlinks` on both the root and the
candidate. That mirrors the Python `os.path.commonpath` check on
resolved paths — symlinks that would otherwise escape `dir` are
detected because the resolved target sits outside the resolved root.

## Layout

```
generated_images/
├── go.mod
├── README.md
├── pkg/generatedimages/
│   ├── resolver.go        # regex, ImageHeaders, Resolve, typed errors
│   └── resolver_test.go   # table-driven coverage + traversal tests
└── cmd/generatedimages-demo/
    └── main.go            # walks happy / not-found / bad-ext / traversal
```

## Demo

```
go run ./cmd/generatedimages-demo
```

Output (abbreviated):

```
== generatedimages demo ==

[image headers]
  Cache-Control: public, max-age=31536000, immutable
  X-Content-Type-Options: nosniff

[happy path]
  filename = "abcdef12.png"
  resolved = "/var/folders/.../T/.../abcdef12.png" (ok)

[missing file]
  filename = "deadbeef.png"
  rejected (not-found): image not found: "deadbeef.png"

[bad extension]
  filename = "abcdef12.exe"
  rejected (filename): invalid filename: "abcdef12.exe"

[traversal attempt]
  filename = "../etc/passwd.png"
  rejected (filename): invalid filename: "../etc/passwd.png"

[empty filename]
  filename = ""
  rejected (filename): invalid filename: ""

[allowed extensions]
  [png jpg jpeg webp gif mp4 mov webm mkv m4v]
```
