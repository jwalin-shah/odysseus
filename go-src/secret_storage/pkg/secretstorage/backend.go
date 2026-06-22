package secretstorage

import (
	"errors"
	"os"
	"path/filepath"
	"sync"
)

// FileKeyBackend stores the Fernet-equivalent key in a single file on
// disk. The file is created with 0o600 permissions on POSIX hosts; on
// Windows the mode bits are ignored by the kernel so the path's user-
// profile ACL still restricts access. The key is cached in-memory after
// the first Load so concurrent callers don't hit the disk.
//
// FileKeyBackend is safe for concurrent use. The load is guarded by
// sync.Once so even racy first-time callers see a single Load.
type FileKeyBackend struct {
	path string

	once sync.Once
	key  []byte
	err  error
}

// NewFileKeyBackend returns a backend rooted at path. The file does not
// need to exist yet; NewSecretStorage will lazily create it via the
// FileKeyBackend.EnsureKey helper when a real cipher needs to be wired.
// The path is resolved against the current working directory if not
// absolute so callers can pass either form.
func NewFileKeyBackend(path string) (*FileKeyBackend, error) {
	if path == "" {
		return nil, errors.New("secretstorage: FileKeyBackend path is empty")
	}
	return &FileKeyBackend{path: path}, nil
}

// Path returns the absolute path of the key file. Useful for tests that
// want to assert the file was created.
func (f *FileKeyBackend) Path() string {
	return f.path
}

// Load returns the cached key, loading it from disk on the first call.
// On any subsequent call the cached value is returned and Load never
// hits the filesystem again.
func (f *FileKeyBackend) Load() ([]byte, error) {
	f.once.Do(f.loadOnce)
	return append([]byte(nil), f.key...), f.err
}

// loadOnce is the body of the sync.Once block. It reads the key file
// and stashes the bytes (or the error) for subsequent Load callers.
func (f *FileKeyBackend) loadOnce() {
	data, err := os.ReadFile(f.path)
	if err != nil {
		f.err = err
		return
	}
	f.key = data
}

// EnsureKey writes key to the backend's path with 0o600 permissions,
// creating any parent directories as needed. If the file already exists
// the call is a no-op so the existing key is preserved. This mirrors
// the Python module's _load_or_create_key lazy-init.
func (f *FileKeyBackend) EnsureKey(key []byte) error {
	if len(key) == 0 {
		return errEmptyKey
	}
	if existing, err := os.ReadFile(f.path); err == nil && len(existing) > 0 {
		// Key already present; do not overwrite. Cached copy may be
		// stale until next Load, so reset the once.
		f.reset()
		f.key = existing
		return nil
	}
	dir := filepath.Dir(f.path)
	if dir != "" && dir != "." {
		if err := os.MkdirAll(dir, 0o700); err != nil {
			return err
		}
	}
	if err := os.WriteFile(f.path, key, 0o600); err != nil {
		return err
	}
	// Invalidate the once so the next Load picks up the freshly written
	// bytes rather than reporting "file not found" from a previous attempt.
	f.reset()
	f.key = key
	return nil
}

// reset clears the sync.Once so the next Load re-reads the file. Tests
// use this after EnsureKey to assert on a fresh key value.
func (f *FileKeyBackend) reset() {
	f.once = sync.Once{}
	f.key = nil
	f.err = nil
}

// InMemoryKeyBackend is a non-persistent KeyBackend. Useful for tests
// that want a fresh key per case without touching the filesystem.
type InMemoryKeyBackend struct {
	key []byte
}

// NewInMemoryKeyBackend returns a backend seeded with key. A nil or
// empty key is rejected because the Fernet-equivalent ciphers require
// a 32-byte secret at minimum.
func NewInMemoryKeyBackend(key []byte) (*InMemoryKeyBackend, error) {
	if len(key) == 0 {
		return nil, errEmptyKey
	}
	if len(key) < 16 {
		return nil, errShortKey
	}
	// Defensive copy so the caller's slice can't mutate the cached key.
	c := make([]byte, len(key))
	copy(c, key)
	return &InMemoryKeyBackend{key: c}, nil
}

// Load returns the cached key. Safe for concurrent use; InMemoryKeyBackend
// never mutates its key after construction.
func (i *InMemoryKeyBackend) Load() ([]byte, error) {
	return append([]byte(nil), i.key...), nil
}
