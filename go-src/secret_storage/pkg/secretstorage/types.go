// Package secretstorage is the Go port of src/secret_storage.py.
//
// It exposes a SecretStorage type with Encrypt / Decrypt / IsEncrypted
// methods that mirror the module-level functions in the Python source.
// The Fernet cipher is abstracted behind a Cipher interface so the
// orchestrator logic (prefix handling, idempotency, error fallback) can
// be exercised without a crypto dependency. A production deployment
// should provide a Fernet-equivalent Cipher; the default shipped here
// is a documented test-grade XOR stub.
//
// All values returned by Encrypt are prefixed with the package-level
// EncryptedPrefix constant ("enc:") so a downstream caller can
// distinguish ciphertext from plaintext at a glance. This matches the
// Python module's behavior so existing migration logic stays portable.
package secretstorage

// EncryptedPrefix is the literal byte sequence prepended to every
// ciphertext token produced by SecretStorage.Encrypt. It is exported so
// callers can branch on IsEncrypted / strip-and-decrypt without copying
// the string literal.
const EncryptedPrefix = "enc:"

// Cipher is the encryption primitive SecretStorage depends on. The
// interface is deliberately minimal: encrypt a UTF-8 plaintext into a
// URL-safe ASCII token, decrypt the token back to UTF-8 plaintext.
//
// Production implementations should use a Fernet-equivalent (AES-128-CBC
// + HMAC-SHA256 + URL-safe base64 with versioned header). The XOR stub
// shipped in this package is documented as insecure and intended only
// for orchestrator-level tests.
//
// Encrypt must never return a value that begins with EncryptedPrefix;
// SecretStorage.Encrypt pre-pends the prefix itself so the orchestrator
// logic is the single source of truth for the marker.
type Cipher interface {
	Encrypt(plaintext string) (string, error)
	Decrypt(token string) (string, error)
}

// KeyBackend is the storage abstraction for the symmetric key the
// Cipher needs. A SecretStorage is constructed with one of these; the
// concrete implementation decides whether the key lives on disk (with
// 0o600 POSIX permissions), in memory, or behind a secret manager.
//
// Load must return the key exactly once per SecretStorage lifetime; it
// is the contract that lets NewSecretStorage validate that a key exists
// before any cipher operation is attempted.
type KeyBackend interface {
	Load() ([]byte, error)
}

// SecretStorage is the Go equivalent of the module-level helpers in
// src/secret_storage.py. It is safe for concurrent use: the underlying
// Cipher and KeyBackend are read-only after construction, and the
// (optional) cached key in FileKeyBackend is guarded by sync.Once.
//
// Zero-value SecretStorage is NOT usable; always go through
// NewSecretStorage so the Cipher is initialized.
type SecretStorage struct {
	cipher Cipher
}

// NewSecretStorage loads the key from backend and constructs a
// SecretStorage ready for Encrypt / Decrypt / IsEncrypted calls. The
// key is loaded eagerly so a misconfigured backend fails fast at
// construction time rather than on the first encrypt/decrypt call.
func NewSecretStorage(backend KeyBackend, cipher Cipher) (*SecretStorage, error) {
	if backend == nil {
		return nil, errNilBackend
	}
	if cipher == nil {
		return nil, errNilCipher
	}
	// Touch the backend so a missing/unreadable key surfaces here.
	if _, err := backend.Load(); err != nil {
		return nil, err
	}
	return &SecretStorage{cipher: cipher}, nil
}
