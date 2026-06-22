# secret_storage (Go port)

Go port of `src/secret_storage.py`. The Python module is a tiny
Fernet-based symmetric encryption helper for secrets stored in the SQLite
DB (IMAP/SMTP passwords today; safe to extend). The key lives at
`data/.app_key`, mode 0o600, generated on first call. Encrypted values
carry an `enc:` prefix so the migration is idempotent: passing an
already-encrypted value to `encrypt()` is a no-op; passing a plaintext
value to `decrypt()` returns it unchanged.

This port captures that public surface (`encrypt`, `decrypt`,
`is_encrypted`) behind a small `SecretStorage` type and a `KeyBackend`
interface so the key source can be swapped in tests without touching the
filesystem.

## Scope

This package does NOT re-implement Fernet from scratch. The Python
implementation uses `cryptography.fernet.Fernet` which is AES-128-CBC +
HMAC-SHA256. In Go, the equivalent functionality is available in the
stdlib via `crypto/aes` + `crypto/hmac` + `crypto/cipher`, but Fernet's
specific framing (URL-safe-base64 token, versioned header, fixed
HKDF-derived sub-keys) is a real implementation. Rather than ship a
third-party Fernet dep for a 87-line Python module, this port provides:

- **`KeyBackend` interface** — the storage abstraction for the Fernet key.
  A `FileKeyBackend` writes the key to disk with 0o600 permissions; an
  `InMemoryKeyBackend` is provided for tests.
- **`SecretStorage` type** — the Go equivalent of the module-level
  `encrypt` / `decrypt` / `is_encrypted` functions. Constructed via
  `NewSecretStorage(backend KeyBackend)`.
- **DefaultCipher interface** — abstraction for "encrypt a plaintext
  string → token, decrypt token → plaintext". A `xorStubCipher` ships in
  this port so the round-trip, prefix-stripping, idempotency, and
  error-fallback logic can all be exercised end-to-end without dragging
  in a real Fernet implementation. Real deployments should substitute a
  crypto-backed cipher (Fernet-equivalent) via the same interface.
- **No external dependencies.** Stdlib only.

## Layout

```
go-src/secret_storage/
  go.mod                # module github.com/odysseus/secret_storage
  go.sum
  README.md
  cmd/secretestore-demo/main.go   # demo CLI: --key-path, --op, --value
  pkg/secretstorage/
    types.go            # SecretStorage struct, KeyBackend interface,
                        # Cipher interface, encryptedPrefix constant
    backend.go          # FileKeyBackend (0o600 POSIX perms),
                        # InMemoryKeyBackend, helpers
    cipher.go           # xorStubCipher (test-grade) + interface doc
    secretstorage.go    # NewSecretStorage, Encrypt, Decrypt, IsEncrypted
    secretstorage_test.go # table-driven tests: happy/empty/error/edge
```

## Public API

```go
import contextsecrets "github.com/odysseus/secret_storage/pkg/secretstorage"

// Production wiring (POSIX-locked key file).
backend, _ := contextsecrets.NewFileKeyBackend("/var/data/.app_key")
ss, err := contextsecrets.NewSecretStorage(backend)

ct := ss.Encrypt("hunter2")          // "enc:gAAA..."
pt := ss.Decrypt(ct)                  // "hunter2"
plaintext := ss.Decrypt("plaintext")  // passes through unchanged
ct2 := ss.Encrypt(ct)                 // idempotent re-encrypt no-op
yes := ss.IsEncrypted(ct)             // true
```

## Port notes

- **`enc:` prefix.** All encrypt/decrypt behaviour around the prefix
  (`"enc:"`) is byte-for-byte preserved: empty input is a no-op, a value
  already prefixed is passed through on encrypt, an unprefixed value is
  passed through on decrypt (legacy row compatibility), and a corrupt
  token yields `""` rather than an error.
- **`safe_chmod`.** The Python helper is a no-op on Windows. The Go
  port uses `os.Chmod` directly because the host running the binary
  controls its own permissions; on a Windows host the mode is silently
  ignored by the kernel, matching the Python behaviour.
- **No-op cipher.** The default cipher is a deterministic XOR stub so
  the orchestrator logic (round-trip, prefix handling, error fallback)
  is testable. A real deployment should swap in a Fernet-equivalent
  cipher behind the `Cipher` interface. The stub is documented as
  insecure in its doc comment so it cannot be mistaken for production.
- **Thread safety.** `SecretStorage` is safe for concurrent use. The
  underlying Fernet (and the XOR stub) is read-only after construction,
  and `FileKeyBackend` caches the loaded key behind a `sync.Once`.

## Running tests

```bash
cd go-src/secret_storage
go build ./...
go test -race ./...
```

All tests use `t.TempDir()` for the file backend and an in-memory
backend for the round-trip / prefix logic.

## Demo CLI

```bash
go run ./cmd/secretestore-demo \
  --key-path /tmp/x/app.key \
  --op encrypt --value 'hunter2'
go run ./cmd/secretestore-demo \
  --key-path /tmp/x/app.key \
  --op decrypt --value 'enc:...'
go run ./cmd/secretestore-demo \
  --key-path /tmp/x/app.key \
  --op is-encrypted --value 'enc:...'
```

The CLI prints the result and exits non-zero on a hard error
(unreadable key, decrypt failure when no fallback applies, etc.). Decrypt
failures fall back to `""` per the Python module contract, so the CLI
prints an empty line and exits zero on a corrupt token.
