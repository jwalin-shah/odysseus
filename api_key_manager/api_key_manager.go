// Package api_key_manager stores per-provider API keys in a single JSON file
// encrypted with a Fernet key living alongside it. It mirrors src/api_key_manager.py.
//
// The encryption key (.key) is created on first use and chmodded 0o600 so it is
// only readable by the owner. On read we re-chmod (heal older installs that
// were written with a looser umask). On Windows os.Chmod is best-effort and
// the bit may be silently ignored — matching the Python safe_chmod semantics.
//
// Files live in the data directory supplied at construction:
//
//	<data_dir>/.key        — Fernet key (URL-safe-base64, 44 chars)
//	<data_dir>/api_keys.json — map of provider -> encrypted token
//
// Save operates on the raw on-disk dict (not on load()'s decrypted form) so
// other providers' values stay encrypted — re-encrypting them with the same
// key works but means a corruption event would lose every provider at once.
package api_key_manager

import (
	"encoding/json"
	"errors"
	"fmt"
	"log"
	"os"
	"path/filepath"
	"sync"
	"time"
)

// Logger is the package-level logger used for non-fatal warnings (corrupt
// files, skipped providers). Defaults to the stdlib default logger so the
// package is usable without explicit wiring; callers can swap it.
var Logger = log.Default()

// keyFilePerm is the mode set on the .key file. 0o600 = owner read/write only.
// The key decrypts every stored provider credential so it must not be
// group/world-readable.
const keyFilePerm os.FileMode = 0o600

// keysFilePerm is set on api_keys.json. The tokens inside are encrypted, but
// we still keep this owner-only for defence in depth.
const keysFilePerm os.FileMode = 0o600

// keyFileName and keysFileName are the on-disk filenames inside data_dir.
const (
	keyFileName  = ".key"
	keysFileName = "api_keys.json"
)

// Manager owns the data directory and the on-disk paths derived from it. It
// is safe for concurrent use — the internal mutex serialises key generation
// and the file I/O that follows.
type Manager struct {
	dataDir     string
	keyFile     string
	keysFile    string
	mu          sync.Mutex
	cachedKey   []byte // URL-safe base64 bytes of the Fernet key
	cachedKeyOK bool
}

// NewManager returns a Manager rooted at dataDir. The directory must exist
// (we do not auto-create it — Python also relied on the caller to ensure the
// data directory exists). Use os.MkdirAll before calling if needed.
func NewManager(dataDir string) *Manager {
	return &Manager{
		dataDir:  dataDir,
		keyFile:  filepath.Join(dataDir, keyFileName),
		keysFile: filepath.Join(dataDir, keysFileName),
	}
}

// DataDir returns the directory the Manager was constructed with. Exposed
// for the CLI so it can print the .key path.
func (m *Manager) DataDir() string { return m.dataDir }

// KeyFile returns the absolute path of the .key file.
func (m *Manager) KeyFile() string { return m.keyFile }

// KeysFile returns the absolute path of the api_keys.json file.
func (m *Manager) KeysFile() string { return m.keysFile }

// GetOrCreateKey returns the Fernet key bytes (URL-safe-base64 encoded string,
// 44 chars). On first call it generates a fresh key, writes it 0o600, and
// returns the bytes. On subsequent calls it re-chmods the existing file to
// 0o600 (heals older installs) and returns the cached/read value.
func (m *Manager) GetOrCreateKey() ([]byte, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.cachedKeyOK {
		return m.cachedKey, nil
	}

	if _, err := os.Stat(m.keyFile); err == nil {
		// Heal older installs that were written under a looser umask
		// (often 0o644 on shared dev hosts). Best-effort: ignore
		// permission errors on platforms that don't expose the mode bit.
		_ = safeChmod(m.keyFile, keyFilePerm)
		data, err := os.ReadFile(m.keyFile)
		if err != nil {
			return nil, fmt.Errorf("api_key_manager: read %s: %w", m.keyFile, err)
		}
		m.cachedKey = data
		m.cachedKeyOK = true
		return data, nil
	} else if !errors.Is(err, os.ErrNotExist) {
		return nil, fmt.Errorf("api_key_manager: stat %s: %w", m.keyFile, err)
	}

	// Generate. GenerateKey itself can fail only on rand.Read failure.
	key, err := GenerateKey()
	if err != nil {
		return nil, err
	}
	if err := os.WriteFile(m.keyFile, key, keyFilePerm); err != nil {
		return nil, fmt.Errorf("api_key_manager: write %s: %w", m.keyFile, err)
	}
	_ = safeChmod(m.keyFile, keyFilePerm)
	m.cachedKey = key
	m.cachedKeyOK = true
	return key, nil
}

// EncryptAPIKey seals plaintext under the manager's Fernet key. An empty
// plaintext returns an empty token (matches Fernet-no-op semantics in the
// Python code).
func (m *Manager) EncryptAPIKey(plaintext string) (string, error) {
	if plaintext == "" {
		return "", nil
	}
	key, err := m.GetOrCreateKey()
	if err != nil {
		return "", err
	}
	tok, err := Encrypt(key, []byte(plaintext), time.Now())
	if err != nil {
		return "", fmt.Errorf("api_key_manager: encrypt: %w", err)
	}
	return string(tok), nil
}

// DecryptAPIKey unseals a token previously produced by EncryptAPIKey. An
// empty token returns the empty string. Any decryption failure returns
// ErrInvalidToken so load() can log-and-skip without distinguishing failure
// modes.
func (m *Manager) DecryptAPIKey(token string) (string, error) {
	if token == "" {
		return "", nil
	}
	key, err := m.GetOrCreateKey()
	if err != nil {
		return "", err
	}
	plain, err := Decrypt(key, []byte(token), time.Now())
	if err != nil {
		return "", err
	}
	return string(plain), nil
}

// Save encrypts apiKey under the manager's key and writes it into the JSON
// store under provider. Other providers' values are preserved as-is (still
// encrypted) so a partial file corruption only loses the one being saved.
//
// load() round-trips through plaintext, so using it would silently re-encrypt
// every other provider with the same key — still correct, but it widens the
// blast radius of a transient error. _loadRaw mirrors the Python original.
func (m *Manager) Save(provider string, apiKey string) error {
	enc, err := m.EncryptAPIKey(apiKey)
	if err != nil {
		return err
	}
	m.mu.Lock()
	defer m.mu.Unlock()
	keys, err := m.loadRawLocked()
	if err != nil {
		return err
	}
	keys[provider] = enc
	return m.writeKeysLocked(keys)
}

// Load returns the decrypted map of provider -> apiKey. Entries that fail to
// decrypt are skipped (logged at warning level) — matches Python's
// InvalidToken/ValueError catch.
func (m *Manager) Load() (map[string]string, error) {
	m.mu.Lock()
	raw, err := m.loadRawLocked()
	m.mu.Unlock()
	if err != nil {
		return nil, err
	}
	out := make(map[string]string, len(raw))
	for provider, tok := range raw {
		plain, err := m.DecryptAPIKey(tok)
		if err != nil {
			Logger.Printf("api_key_manager: failed to decrypt API key for %s: %v", provider, err)
			continue
		}
		out[provider] = plain
	}
	return out, nil
}

// loadRaw reads api_keys.json from disk, tolerating missing/corrupt/wrong-
// shaped files by returning an empty map. Any failure logs a warning.
//
// The caller must NOT hold m.mu — this method takes the lock itself.
func (m *Manager) loadRaw() (map[string]string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()
	return m.loadRawLocked()
}

// loadRawLocked is loadRaw's inner; the caller holds m.mu.
func (m *Manager) loadRawLocked() (map[string]string, error) {
	if _, err := os.Stat(m.keysFile); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return map[string]string{}, nil
		}
		return nil, fmt.Errorf("api_key_manager: stat %s: %w", m.keysFile, err)
	}
	data, err := os.ReadFile(m.keysFile)
	if err != nil {
		return nil, fmt.Errorf("api_key_manager: read %s: %w", m.keysFile, err)
	}
	if len(data) == 0 {
		return map[string]string{}, nil
	}
	var raw map[string]any
	if err := json.Unmarshal(data, &raw); err != nil {
		// Corrupt/truncated JSON — startup-critical, treat as no keys.
		Logger.Printf("api_key_manager: failed to parse %s: %v", m.keysFile, err)
		return map[string]string{}, nil
	}
	if raw == nil {
		return map[string]string{}, nil
	}
	out := make(map[string]string, len(raw))
	for k, v := range raw {
		s, ok := v.(string)
		if !ok {
			// Filter to string-valued entries (matches Python).
			continue
		}
		out[k] = s
	}
	return out, nil
}

// writeKeysLocked persists the (already-encrypted) keys map. Caller holds
// m.mu.
func (m *Manager) writeKeysLocked(keys map[string]string) error {
	data, err := json.MarshalIndent(keys, "", "  ")
	if err != nil {
		return fmt.Errorf("api_key_manager: marshal keys: %w", err)
	}
	if err := os.WriteFile(m.keysFile, data, keysFilePerm); err != nil {
		return fmt.Errorf("api_key_manager: write %s: %w", m.keysFile, err)
	}
	_ = safeChmod(m.keysFile, keysFilePerm)
	return nil
}

// safeChmod calls os.Chmod and ignores ErrPermission (or any other error) —
// matching safe_chmod's "try to set, ignore on platforms where the bit is
// meaningless" contract. On Windows the underlying syscall only sets the
// read-only bit, so most chmods return errors which we treat as success.
func safeChmod(path string, mode os.FileMode) error {
	err := os.Chmod(path, mode)
	if err == nil {
		return nil
	}
	if errors.Is(err, os.ErrPermission) {
		return nil
	}
	// Other errors (e.g. ENOSYS on a stub filesystem, or ENOTDIR) are
	// surfaced so the caller can decide — but the only caller (GetOrCreateKey)
	// intentionally ignores the return value.
	return err
}
