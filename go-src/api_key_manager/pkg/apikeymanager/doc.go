// Package apikeymanager is the Go port of src/api_key_manager.py. It is a
// tiny Fernet-backed key/value store for per-provider API keys, rooted in a
// caller-supplied data directory:
//
//	<dataDir>/.key          — Fernet symmetric key (32 url-safe base64
//	                          bytes raw = 256 bits), created on first use
//	                          with mode 0o600.
//	<dataDir>/api_keys.json — JSON map of provider -> Fernet ciphertext.
//	                          Only the value being written is re-encrypted
//	                          on each Save; the other providers' ciphertexts
//	                          are preserved as-is so other providers never
//	                          get decrypted-to-plaintext at rest.
//
// The Python module uses cryptography.fernet.Fernet directly; on the Go side
// we provide a thin fernetEncode / fernetDecode pair built on stdlib only
// (crypto/aes + crypto/hmac + crypto/sha256 + encoding/base64). Fernet is a
// stable, simple framing (Version || Timestamp || IV || Ciphertext || HMAC,
// all base64url-encoded). See https://github.com/fernet/spec/blob/master/Spec.md
// for the wire-format spec this implementation conforms to.
//
// The port preserves the Python module's public surface verbatim:
//
//	APIKeyManager(data_dir)  -> New(dataDir) *Manager
//	get_or_create_key()      -> mgr.EnsureKey() (called internally)
//	encrypt_api_key(s)       -> mgr.EncryptAPIKey(s) (string, error)
//	decrypt_api_key(s)       -> mgr.DecryptAPIKey(s) (string, error)
//	save(provider, key)      -> mgr.Save(provider, key) error
//	load()                   -> mgr.Load() (map[string]string, error)
//
// Out of scope: the Python module imports core.platform_compat.safe_chmod
// which is a no-op on Windows. The Go port calls os.Chmod unconditionally
// and lets the OS ignore the mode bits where they are meaningless — matches
// the wave3 reference port's behaviour and the wave9 secret_storage module.
//
// # Concurrency
//
// *Manager is safe for concurrent use. The cached Fernet key is guarded by
// a sync.RWMutex so readers don't block each other; the on-disk
// api_keys.json is read and rewritten on every Save/Load call (matching the
// Python source, which treats the file as the source of truth and does not
// keep an in-memory mirror). go test -race ./... exercises concurrent
// Encrypt/Save/Load callers and the race detector must stay clean.
package apikeymanager
