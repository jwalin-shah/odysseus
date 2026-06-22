# api_key_manager (Go port)

Go port of `src/api_key_manager.py`. Stores per-provider API keys in a single
JSON file (`api_keys.json`) encrypted with a key (`.key`) living alongside it.

## Scope

Mirrors the Python module's public surface:

| Python                              | Go                                                |
|-------------------------------------|---------------------------------------------------|
| `APIKeyManager(data_dir)`           | `New(data_dir) *Manager`                          |
| `get_or_create_key()` -> `bytes`    | `GetOrCreateKey() ([]byte, error)`                |
| `encrypt_api_key(s) -> str`         | `EncryptAPIKey(s) (string, error)`                |
| `decrypt_api_key(s) -> str`         | `DecryptAPIKey(s) (string, error)`                |
| `save(provider, api_key)`           | `Save(provider, api_key) error`                   |
| `load() -> dict`                    | `Load() (map[string]string, error)`               |
| `_load_raw() -> dict`               | `LoadRaw() (map[string]string, error)` (exported) |

## Encryption scheme

AES-256-GCM (authenticated encryption with associated data), stdlib-only.

On-disk layout for each token:

```
base64( nonce(12 bytes) || ciphertext || gcm_tag(16 bytes) )
```

The `.key` file is **32 raw bytes** (no base64 wrapper), written 0o600 on
first use.

### Why AES-256-GCM, not Fernet?

Fernet (HMAC-SHA256 + AES-CBC + timestamp + version byte) needs an external
`cryptography` package and brings machinery we don't use — key rotation,
TTL. AES-256-GCM gives us authenticated encryption in one primitive, ships
in the stdlib, and the random 96-bit nonce gives negligible collision risk
for the number of keys a single user stores.

The trade-off: this format is not byte-compatible with the Python Fernet
tokens stored by the previous module. Old `.key` and `api_keys.json` files
must be regenerated on first run after the port ships — the test suite
treats a missing file as an empty load, so the migration cost is bounded.

## Layout

```
go-src/api_key_manager/
  go.mod
  README.md
  cmd/apikeymgr/main.go          # demo CLI: save -> load -> print plaintext
  pkg/apikeymgr/
    manager.go                   # Manager type + New + GetOrCreateKey + Save/Load
    manager_test.go              # roundtrip, multi-provider, fail-soft tests
    aesgcm.go                    # AES-256-GCM primitives + ErrInvalidToken
```

Module path: `github.com/odysseus/api_key_manager`.

## Port notes

- **Raw load then write preserves other providers' ciphertexts.** `Save`
  loads the still-encrypted dict via `LoadRaw`, sets the one entry, and
  writes the whole thing back. Round-tripping through `Load` first would
  decrypt every other provider and write it back as plaintext, then fail
  to decrypt on the next `Load`. The Python original uses the same pattern.
- **chmod 0o600 on read heals older installs.** Older versions of the
  Python module wrote `.key` under the process umask (often 0o644 on shared
  hosts). `GetOrCreateKey` re-chmods the existing file on every read so the
  permissions tighten without a key rotation. On non-Unix platforms the
  chmod is a no-op (Windows ACLs already restrict to the user).
- **Fail-soft on corrupt / wrong-shape files.** `LoadRaw` returns an empty
  map and logs a warning when `api_keys.json` is missing, empty, corrupt
  JSON, or a non-dict shape (e.g. a JSON list). `Load` then returns an
  empty dict. Individual bad tokens (bad base64, AEAD tag mismatch) are
  skipped with a warning so a partial corruption doesn't drop every
  provider.
- **Empty in, empty out.** `EncryptAPIKey("")` and `DecryptAPIKey("")` both
  return `""` without touching disk.

## Build and test

```sh
cd go-src/api_key_manager
go build ./...
go test -race ./...
```
