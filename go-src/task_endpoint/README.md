# task_endpoint (Go port)

Go port of `src/task_endpoint.py` — the small helper that resolves which
endpoint, model, and headers background-task callers (auto-naming, memory
writes, scheduled jobs, etc.) should use.

The Python source is a one-line wrapper around `src/endpoint_resolver.py`:

```python
def resolve_task_endpoint(fallback_url=None, fallback_model=None, fallback_headers=None, owner=None):
    return resolve_endpoint("task", fallback_url, fallback_model, fallback_headers, owner=owner)
```

This Go port keeps the same contract but lives in its own module so it can
be reused without pulling the whole Odysseus graph. It has **zero external
dependencies** and no I/O: the caller supplies a pre-populated `Settings`
struct (or an empty one) and the resolver picks the admin path or the
fallback path the same way the Python version does.

## What this package does

`taskendpoint.Resolve` returns a `Resolution{URL, Model, Headers, Source}`
tuple. The `Source` field makes the resolver's branch visible:

- `admin` — admin settings configured the task endpoint; the admin URL
  and model were used (fallback model is used when admin does not pin
  one; fallback headers are merged under admin headers).
- `fallback` — no admin settings, fallbacks supplied; the caller's
  fallback URL, model, and headers are returned verbatim (copied, so
  the caller cannot accidentally mutate the fallback map).
- `empty` — nothing configured and nothing supplied; `URL` and `Model`
  are empty strings and `Headers` is nil. Callers should treat this as
  "no endpoint available" exactly like the Python version, where
  `resolve_endpoint` returns its fallbacks (which may be `None`).

## Public API

```go
type Settings struct {
    EndpointID      string
    EndpointURL     string
    EndpointModel   string
    EndpointHeaders map[string]string
}

type Resolution struct {
    URL     string
    Model   string
    Headers map[string]string
    Source  string // "admin" | "fallback" | "empty"
}

func Resolve(settings Settings, fallbackURL, fallbackModel string, fallbackHeaders map[string]string, owner string) Resolution
```

`owner` is accepted for parity with the Python signature. This in-memory
port does not consume it; the persistence-layer callers thread it into
the admin-settings DB query the same way `src/endpoint_resolver.py` does.

## Header merging

When both admin and fallback headers are present, the admin value wins
on key conflict (Python's `dict.update` semantics, which is what the
underlying `resolve_endpoint` uses). Non-conflicting keys from both maps
are preserved.

## Layout

```
task_endpoint/
├── go.mod
├── README.md
├── pkg/taskendpoint/
│   ├── resolver.go        # Settings, Resolution, Resolve
│   └── resolver_test.go   # table-driven coverage of all three paths
└── cmd/taskendpoint-demo/
    └── main.go            # walks the three resolution paths
```

## Demo

```
go run ./cmd/taskendpoint-demo
```

Output (abbreviated):

```
== taskendpoint demo ==

[admin wins]
  source = admin
  url    = "https://admin.example/v1"
  model  = "admin-model"
  headers:
    - X-Admin: yes
    - Authorization: Bearer xyz

[fallback]
  source = fallback
  url    = "https://fallback.example/v1"
  model  = "fallback-model"
  headers:
    - Authorization: Bearer xyz

[empty]
  source = empty
  url    = ""
  model  = ""
  headers: (none)
```
