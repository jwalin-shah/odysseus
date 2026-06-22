# api_key_manager (Go port)

Go port of [`src/api_key_manager.py`](../../src/api_key_manager.py). The
Python module is a tiny Fernet-backed key/value store for per-provider API
keys, rooted in a caller-supplied data directory:

```
<data_dir>/.key          — Fernet symmetric key (url-safe base64)
<data_dir>/api_keys.json — JSON map of provider -> Fernet ciphertext
```

The `.key` file is generated on first use with mode 0o600; pre-existing
files with a looser mode are healed to 0o600 on read. The
`api_keys.json` is created lazily on the first Save.

## Mapping (Python → Go)

| Python (`src/api_key_manager.py`)        | Go (`github.com/odysseus/api_key_manager/pkg/apikeymanager`) |
|------------------------------------------|----------------------------------------------------------------|
| `APIKeyManager(data_dir)`                | `New(dataDir) (*Manager, error)`                               |
| `get_or_create_key()` (internal)         | `Manager.ensureKey()` (called from `New`)                      |
| `encrypt_api_key(s)` -> `str`            | `Manager.EncryptAPIKey(s) (string, error)`                    |
| `decrypt_api_key(s)` -> `str`            | `Manager.DecryptAPIKey(s) (string, error)`                    |
| `save(provider, api_key)`                | `Manager.Save(provider, apiKey) error`                         |
| `load()` -> `Dict[str, str]`             | `Manager.Load() (map[string]string, error)`                    |
| `_load_raw()` (internal)                 | `Manager.loadRaw()` (private; same shape)                      |
| `cryptography.fernet.InvalidToken`       | `ErrInvalidToken` (errors.Is)                                  |
| `json.JSONDecodeError` / wrong shape     | `ErrCorruptStore` (errors.Is)                                  |
| `os errors` (missing file etc.)          | stdlib `*PathError`; `errors.Is(err, fs.ErrNotExist)` still works |

The Python class methods are renamed to Go-idiomatic names
(`encrypt_api_key` → `EncryptAPIKey`, `load` → `Load`). Behaviour is
preserved exactly:

- `""` round-trips to `""` without a Fernet round-trip (the Python helper
  has the same fast-path; encrypted empty values would round-trip
  identically but the empty-string convention matches the source
  verbatim).
- `Save` reads the on-disk dict *still encrypted* and re-writes it; it
  never decrypts other providers' tokens. The Python source has the
  same shape — re-encrypting the entire map would be wasted work and
  would risk losing other providers' ciphertexts to a single
  corruption event.
- `Load` swallows per-provider decrypt failures (matching the Python
  `logger.warning` path). A corrupt store returns `(map{},
  ErrCorruptStore)`.

## Encryption scheme

Fernet (HMAC-SHA256 + AES-128-CBC + 64-bit timestamp + version byte),
stdlib only. Token wire format:

```
base64url( version(1) || timestamp(8) || iv(16) || ciphertext(N*16) || hmac(32) )
```

The Fernet spec is stable, simple, and the framing is easy to reproduce
on top of `crypto/aes` + `crypto/hmac` + `crypto/sha256` +
`encoding/base64`. See
[the Fernet spec](https://github.com/fernet/spec/blob/master/Spec.md) for
the wire format this implementation conforms to.

The Python module stores the key in `.key` as the url-safe base64 string
that `Fernet.generate_key()` produces. The Go port writes the same form
so a `.key` file written by either side is readable by the other.

## Concurrency

`*Manager` is safe for concurrent use. The cached Fernet key is guarded
by `sync.RWMutex` so parallel `Encrypt`/`Decrypt` callers don't block
each other; the on-disk `api_keys.json` is read and rewritten on every
`Save`/`Load` call (matching the Python source, which treats the file
as the source of truth and does not keep an in-memory mirror).
`go test -race ./...` exercises concurrent `Encrypt`/`Save`/`Load`
callers and the race detector must stay clean.

## Layout

```
go-src/api_key_manager/
  go.mod                       # module github.com/odysseus/api_key_manager, go 1.22
  README.md                    # this file
  pkg/apikeymanager/
    doc.go                     # package doc comment
    errors.go                  # ErrInvalidToken, ErrCorruptStore, ErrDataDirEmpty, ErrEmptyProvider
    fernet.go                  # encodeFernetKey, decodeFernetKey, fernetEncode, fernetDecode
    pkcs7.go                   # PKCS#7 padding helpers
    rand.go                    # crypto/rand indirection (tests can override)
    clock.go                   # nowSeconds indirection (tests can override)
    atomic.go                  # atomicWrite helper (temp file + fsync + rename)
    manager.go                 # Manager, New, DataDir, KeyFilePath, APIKeysFilePath,
                               # EncryptAPIKey, DecryptAPIKey, Save, Load
    apikeymanager_test.go      # table-driven tests + race smoke + corrupt-store path
  cmd/apikeymanager-demo/
    main.go                    # --data-dir / --provider / --value / --decrypt / --list CLI
```

## Public API

```go
import (
    apikm "github.com/odysseus/api_key_manager/pkg/apikeymanager"
)

mgr, err := apikm.New("/var/lib/odysseus")
if err != nil { /* inspect: ErrDataDirEmpty, ErrInvalidToken, fs errors */ }

ct, err := mgr.EncryptAPIKey("BSAhunter2")
if err != nil { /* inspect: ErrInvalidToken (malformed key file) */ }

if err := mgr.Save("brave", "BSAhunter2"); err != nil { /* … */ }

keys, err := mgr.Load()
if err != nil && !apikm.IsCorruptStore(err) { /* real error */ }
for provider, plain := range keys {
    _ = provider; _ = plain
}

// Direct encrypt/decrypt (no disk I/O):
ct, err := mgr.EncryptAPIKey("sk-test")
pt, err := mgr.DecryptAPIKey(ct)

// Paths:
fmt.Println(mgr.DataDir(), mgr.KeyFilePath(), mgr.APIKeysFilePath())
```

## Sentinel errors

| Sentinel              | When                                                        | Python equivalent                       |
|-----------------------|-------------------------------------------------------------|-----------------------------------------|
| `ErrInvalidToken`     | Fernet decode / HMAC failure / wrong key length             | `cryptography.fernet.InvalidToken`      |
| `ErrCorruptStore`     | `api_keys.json` is missing-truncated / wrong-shaped         | `json.JSONDecodeError` + wrong-shape log|
| `ErrDataDirEmpty`     | `New("")`                                                   | n/a (Python would silently join)        |
| `ErrEmptyProvider`    | `Save("", _)`                                               | n/a (Python would write empty key)      |

Use `errors.Is` to test. The convenience `IsCorruptStore(err)` is
exposed so trivial call sites don't have to import `errors`.

## Out of scope

- **Flask integration**: the Python module is consumed by
  `routes/personal_routes.py` and friends. The Go port exposes the same
  surface but does not wrap a Flask handler. Callers (the Odysseus Go
  server, or a future Python-side adapter) wire it up directly.
- **Cross-language key reuse**: the `.key` file is byte-compatible
  with `cryptography.fernet.Fernet` (same url-safe base64, same 32 raw
  bytes). The `api_keys.json` ciphertexts are also byte-compatible
  (Fernet tokens are deterministic given the key and IV), so a Go
  port of this module can load a Python-written store and vice-versa.
- **Key rotation**: Fernet's spec supports it; the Python module does
  not implement it, and neither does this port.
- **TTL / timestamp validation**: the timestamp field is informational
  only; the receiver does not reject stale tokens (matching the Python
  `cryptography.fernet.Fernet` default — TTL is opt-in via
  `Fernet(..., ttl=...)` and not used here).

## Demo CLI

```bash
cd go-src/api_key_manager
go run ./cmd/apikeymanager-demo --data-dir /tmp/akm \
    --provider brave --value 'BSAhunter2'
# op=save provider=brave plain_len=10 decrypt_len=10 prefix=BSAh...
# roundtrip=ok

go run ./cmd/apikeymanager-demo --data-dir /tmp/akm --provider brave --decrypt
# op=decrypt provider=brave plain_len=10 decrypt_len=10 prefix=BSAh...
# roundtrip=skipped (no plaintext available)

go run ./cmd/apikeymanager-demo --data-dir /tmp/akm --list
# providers=1
#   - brave (len=10 prefix=BSAh...)
```

The CLI never prints the full key — only a 4-char prefix and length
metadata, matching the Python module's "no-log" convention.

## Running tests

```bash
cd go-src/api_key_manager
go build ./...
go test -race ./...
go vet ./...
```

Tests use only the stdlib `testing`, `errors`, and `strings` packages,
plus a frozen-clock helper (`withFrozenClock`) to keep Fernet token
timestamps deterministic. There is no network, no fixture files, and
no global state.
