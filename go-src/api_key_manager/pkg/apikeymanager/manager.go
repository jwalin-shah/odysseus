package apikeymanager

import (
	"crypto/rand"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sync"
)

// apiKeysFileName is the JSON file that stores the provider -> ciphertext
// mapping. The Python module hard-codes this; we expose it as a const so
// tests can assert on the path without duplicating the literal.
const apiKeysFileName = "api_keys.json"

// keyFileName is the symmetric key file. Same convention as the Python
// module.
const keyFileName = ".key"

// fileModeKey is the POSIX mode applied to .key on read and creation.
// The Python safe_chmod helper no-ops on Windows; the Go port applies the
// mode unconditionally and lets the OS ignore it where the permission
// bits are meaningless (matches the existing secret_storage.go
// FileKeyBackend behaviour).
const fileModeKey os.FileMode = 0o600

// fileModeKeys is the mode applied to api_keys.json. The tokens are
// encrypted, but the file is kept owner-only for defence in depth.
const fileModeKeys os.FileMode = 0o600

// Manager is the Go equivalent of src.api_key_manager.APIKeyManager. It
// owns two files inside a data directory:
//
//   - dataDir/.key          — Fernet symmetric key (url-safe base64).
//   - dataDir/api_keys.json — JSON map of provider -> ciphertext.
//
// Safe for concurrent use. The key is loaded once on construction (or
// generated, written with 0o600, and cached); subsequent Encrypt/Decrypt
// calls hit the cached key. api_keys.json is read on every Load/Save call
// — there is no in-memory mirror because the Python source treats the
// on-disk file as the source of truth and the rest of the codebase calls
// load() at startup, not on every read.
//
// Zero-value Manager is not usable; always construct via New.
type Manager struct {
	// dataDir is the directory holding .key and api_keys.json. Stored so
	// callers can introspect via DataDir() and so test fixtures can
	// reference it without re-passing the path.
	dataDir string

	// keyFile and apiKeysFile are absolute paths to the two on-disk
	// artifacts. Joined at construction so per-call paths don't allocate.
	keyFile     string
	apiKeysFile string

	// key is the cached 32-byte raw Fernet key. Set by New; never
	// mutated afterwards.
	key []byte

	// keyMu guards key reads. The Python module is not concurrent-safe
	// at the APIKeyManager level but the Go port is — readers of the
	// cached key are protected by keyMu so a Save racing with a load()
	// never observes a torn key.
	keyMu sync.RWMutex

	// writeMu serializes the on-disk read+write of api_keys.json. The
	// Python module's save() also has this race (last-writer-wins)
	// but its non-atomic open()+write() can produce a partial file
	// when two goroutines overlap. The Go port's atomicWrite would
	// catch the partial write via the rename step, but the temp file
	// collision still surfaces as a "no such file" error when one
	// rename succeeds while the other is mid-create. Serializing
	// here keeps the file parseable under contention without
	// changing the per-call semantics.
	writeMu sync.Mutex
}

// New constructs a Manager rooted at dataDir. If .key does not exist it
// is generated (32 random bytes) and written with mode 0o600. If .key
// exists it is loaded, its permissions are tightened to 0o600 (matching
// the Python safe_chmod heal-on-read behaviour), and its contents are
// used as the Fernet key. The api_keys.json file is not touched here —
// it is created lazily on the first Save.
//
// dataDir is created with mode 0o700 if it does not exist. Pass an
// absolute path to avoid CWD-relative surprises (the Python module does
// not resolve relative paths either; we mirror that behaviour by joining
// the caller's path verbatim).
func New(dataDir string) (*Manager, error) {
	if dataDir == "" {
		return nil, ErrDataDirEmpty
	}

	// Create the data dir with 0o700 so the key file inherits a
	// restrictive parent. os.MkdirAll is a no-op if the dir exists.
	if err := os.MkdirAll(dataDir, 0o700); err != nil {
		return nil, fmt.Errorf("apikeymanager: mkdir data dir: %w", err)
	}

	m := &Manager{
		dataDir:     dataDir,
		keyFile:     filepath.Join(dataDir, keyFileName),
		apiKeysFile: filepath.Join(dataDir, apiKeysFileName),
	}

	key, err := m.ensureKey()
	if err != nil {
		return nil, err
	}
	m.key = key
	return m, nil
}

// DataDir returns the path that was passed to New. Useful for tests and
// for callers that want to confirm the layout.
func (m *Manager) DataDir() string {
	return m.dataDir
}

// KeyFilePath returns the absolute path to the .key file. Exported so
// test fixtures and operators can verify the layout without coupling to
// the internal filepath.Join.
func (m *Manager) KeyFilePath() string {
	return m.keyFile
}

// APIKeysFilePath returns the absolute path to the api_keys.json file.
func (m *Manager) APIKeysFilePath() string {
	return m.apiKeysFile
}

// ensureKey loads the Fernet key from .key, or generates a new one. On
// read it re-tightens the file mode to 0o600 (mirrors the Python
// safe_chmod heal-on-read path). On create it writes the key with mode
// 0o600 directly via os.WriteFile.
//
// Returns the 32 raw bytes of the Fernet key. The bytes are decoded out
// of the on-disk url-safe base64 form (the Python module stores the key
// in url-safe base64 form in .key; the Go port does the same).
func (m *Manager) ensureKey() ([]byte, error) {
	if info, err := os.Stat(m.keyFile); err == nil && !info.IsDir() {
		// Existing key: re-restrict on read so legacy installs heal.
		_ = os.Chmod(m.keyFile, fileModeKey)
		data, err := os.ReadFile(m.keyFile)
		if err != nil {
			return nil, fmt.Errorf("apikeymanager: read key file: %w", err)
		}
		raw, err := decodeFernetKey(string(data))
		if err != nil {
			return nil, fmt.Errorf("apikeymanager: parse key file: %w", err)
		}
		return raw, nil
	} else if err != nil && !os.IsNotExist(err) {
		return nil, fmt.Errorf("apikeymanager: stat key file: %w", err)
	}

	// Generate a fresh key: 32 random bytes -> url-safe base64 -> write.
	raw := make([]byte, fernetKeyLen)
	if _, err := rand.Read(raw); err != nil {
		return nil, fmt.Errorf("apikeymanager: generate key: %w", err)
	}
	encoded := encodeFernetKey(raw)
	if err := os.WriteFile(m.keyFile, []byte(encoded), fileModeKey); err != nil {
		return nil, fmt.Errorf("apikeymanager: write key file: %w", err)
	}
	_ = os.Chmod(m.keyFile, fileModeKey)
	return raw, nil
}

// EncryptAPIKey encrypts plaintext under the cached Fernet key and returns
// the URL-safe base64 ciphertext. An empty plaintext yields "" (the
// Python helper has the same fast-path; encrypted empty values would
// round-trip to the same plaintext but the empty-string convention matches
// the Python source verbatim).
func (m *Manager) EncryptAPIKey(plaintext string) (string, error) {
	if plaintext == "" {
		return "", nil
	}
	m.keyMu.RLock()
	key := append([]byte(nil), m.key...)
	m.keyMu.RUnlock()
	return fernetEncode(key, []byte(plaintext))
}

// DecryptAPIKey reverses EncryptAPIKey. An empty ciphertext yields ""; a
// non-empty ciphertext that fails the HMAC check or otherwise fails to
// decode returns an error matching errors.Is(., ErrInvalidToken).
//
// The Python module's decrypt_api_key raises InvalidToken; this port
// surfaces the same condition as ErrInvalidToken so callers can use
// errors.Is. The Manager.Load() method swallows this error per provider
// (matching the Python logger.warning path).
func (m *Manager) DecryptAPIKey(ciphertext string) (string, error) {
	if ciphertext == "" {
		return "", nil
	}
	m.keyMu.RLock()
	key := append([]byte(nil), m.key...)
	m.keyMu.RUnlock()
	plain, err := fernetDecode(key, ciphertext)
	if err != nil {
		return "", err
	}
	return string(plain), nil
}

// loadRaw returns the on-disk mapping without decrypting any values.
// Mirrors the Python _load_raw() helper: a missing file yields {}, a
// corrupt file (bad JSON or non-object top-level) yields {} with an
// ErrCorruptStore error attached so callers can branch.
//
// The returned map always has string keys and string values; non-string
// values in the JSON are filtered out (matching the Python
// dict-comprehension "if isinstance(key, str)" guard).
func (m *Manager) loadRaw() (map[string]string, error) {
	data, err := os.ReadFile(m.apiKeysFile)
	if err != nil {
		if os.IsNotExist(err) {
			return map[string]string{}, nil
		}
		return nil, fmt.Errorf("apikeymanager: read store: %w", err)
	}
	if len(data) == 0 {
		return map[string]string{}, nil
	}
	// Decode as a generic map first so we can validate the shape
	// (must be an object, not a list or scalar).
	var raw map[string]json.RawMessage
	if err := json.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("%w: %v", ErrCorruptStore, err)
	}
	out := make(map[string]string, len(raw))
	for provider, v := range raw {
		var s string
		if err := json.Unmarshal(v, &s); err != nil {
			continue
		}
		out[provider] = s
	}
	return out, nil
}

// Save encrypts apiKey under the cached Fernet key and writes the
// provider -> ciphertext mapping to api_keys.json. Other providers'
// entries are preserved verbatim — they are read from disk still
// encrypted and re-written unchanged, so a Save never decrypts other
// providers to plaintext.
//
// The Python module's save() is the same shape — loading via load()
// first would decrypt every value, then writing them back as plaintext
// would silently drop other providers on the next load().
func (m *Manager) Save(provider, apiKey string) error {
	if provider == "" {
		return ErrEmptyProvider
	}
	// Serialize the on-disk read+write. See Manager.writeMu.
	m.writeMu.Lock()
	defer m.writeMu.Unlock()

	ct, err := m.EncryptAPIKey(apiKey)
	if err != nil {
		return err
	}
	raw := make(map[string]string)
	if existing, lerr := m.loadRaw(); lerr == nil {
		for k, v := range existing {
			raw[k] = v
		}
	} else if !IsCorruptStore(lerr) {
		return lerr
	}
	raw[provider] = ct
	buf, err := json.MarshalIndent(raw, "", "  ")
	if err != nil {
		return fmt.Errorf("apikeymanager: marshal store: %w", err)
	}
	// Write atomically: write to a sibling temp file, fsync, rename.
	// Matches the Python module's behaviour (which is a single
	// open() + write() and not atomic, but the Go port is stricter so
	// a partial write can't leave the file truncated).
	if err := atomicWrite(m.apiKeysFile, buf, fileModeKeys); err != nil {
		return fmt.Errorf("apikeymanager: write store: %w", err)
	}
	return nil
}

// Load reads api_keys.json and decrypts every entry. Providers whose
// ciphertext fails to decrypt are silently dropped (matching the Python
// logger.warning path). A corrupt store returns (map{}, ErrCorruptStore)
// — the map is always non-nil.
func (m *Manager) Load() (map[string]string, error) {
	raw, err := m.loadRaw()
	if err != nil {
		if IsCorruptStore(err) {
			return map[string]string{}, err
		}
		return nil, err
	}
	out := make(map[string]string, len(raw))
	for provider, ct := range raw {
		pt, derr := m.DecryptAPIKey(ct)
		if derr != nil {
			// Mirror the Python logger.warning path: skip the bad
			// provider and keep going. Callers who want strict
			// semantics should call DecryptAPIKey directly.
			continue
		}
		out[provider] = pt
	}
	return out, nil
}
