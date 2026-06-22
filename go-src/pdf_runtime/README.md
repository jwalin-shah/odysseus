# pdf_runtime (Go port)

Go port of `src/pdf_runtime.py` — the thin loader that fronts the optional
PyMuPDF dependency used by the PDF viewer.

The Python source is a single function plus a module-level constant:

```python
PDF_VIEWER_PYMUPDF_MISSING = (
    "PDF viewer requires PyMuPDF. Install optional PDF dependencies with "
    "`pip install -r requirements-optional.txt` (PyMuPDF is AGPL-3.0)."
)

def load_pymupdf_for_pdf_viewer():
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(PDF_VIEWER_PYMUPDF_MISSING) from exc
    return fitz
```

PyMuPDF is AGPL-3.0 and is intentionally **not** linked into the main
binary. The Go port preserves the same lazy-load + user-facing setup hint
contract through a `Loader` interface and the package-level `ErrMissing`
sentinel. Operators get the same string from `MissingMessage` that the
Python source ships verbatim.

## What this package does

`pdfruntime` does not import PyMuPDF itself. It defines the **boundary**
that a future cgo / build-tag-gated package will live behind. Today, the
useful surface is:

- `Loader` interface (`Load() (any, error)`) — the seam a real PyMuPDF
  loader plugs into.
- `ErrMissing` — sentinel matched with `errors.Is` to detect the
  "PyMuPDF not installed" path.
- `MissingMessage` — the same human-readable setup hint that ships in
  `PDF_VIEWER_PYMUPDF_MISSING`. Operators grep for this string in logs.
- `MissingError(cause)` — constructs the typed error; equivalent to
  Python's `raise RuntimeError(PDF_VIEWER_PYMUPDF_MISSING) from exc`.
- `FuncLoader(fn)` / `StaticLoader{Value}` / `FailingLoader` — test and
  demo helpers.

## Public API

```go
const MissingMessage = "PDF viewer requires PyMuPDF. ..."

var ErrMissing = errors.New("pymupdf missing")

type Loader interface { Load() (any, error) }
type LoaderFunc func() (any, error)

func FuncLoader(fn func() (any, error)) Loader
func MissingError(cause error) error

type StaticLoader struct{ Value any }
type FailingLoader struct{}
```

## Usage

```go
var load pdfruntime.Loader = pdfruntime.FuncLoader(func() (any, error) {
    // Future: gated by `//go:build with_pymupdf`. Today this just
    // returns ErrMissing so the demo can exercise the user-facing
    // path.
    return nil, pdfruntime.ErrMissing
})

mod, err := load.Load()
if errors.Is(err, pdfruntime.ErrMissing) {
    return http.StatusFailedDependency, pdfruntime.MissingMessage
}
```

## Layout

```
pdf_runtime/
├── go.mod
├── README.md
├── pkg/pdfruntime/
│   ├── loader.go        # Loader, LoaderFunc, MissingError, StaticLoader, FailingLoader
│   └── loader_test.go   # table-driven coverage
└── cmd/pdfruntime-demo/
    └── main.go          # walks success / missing / nil-loader paths
```

## Demo

```
go run ./cmd/pdfruntime-demo
```

Expected output (exit code 3 because the "failing loader" scenario is
expected to surface the missing-dependency signal):

```
== pdfruntime demo ==

[static loader (success)]
  loaded: fitz-handle

[failing loader (PyMuPDF absent)]
  ERR_MISSING: PDF viewer requires PyMuPDF. ...

[nil loader (would surface 501)]
  no loader supplied (would surface 501 in a real handler)
```
