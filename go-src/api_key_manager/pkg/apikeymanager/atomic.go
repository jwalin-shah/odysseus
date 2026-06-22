package apikeymanager

import (
	"fmt"
	"os"
	"path/filepath"
)

// atomicWrite writes data to path with mode by staging through a sibling
// temp file, fsyncing, then renaming. The rename is atomic on POSIX
// filesystems; on Windows os.Rename replaces the destination atomically
// when the destination exists, so the guarantee holds there too.
//
// The Python module's save() is not atomic — a power loss mid-write can
// leave api_keys.json truncated. The Go port tightens that contract so
// production callers don't lose the entire on-disk map on a crash.
func atomicWrite(path string, data []byte, mode os.FileMode) error {
	dir := filepath.Dir(path)
	tmp, err := os.CreateTemp(dir, ".api_keys.*.json.tmp")
	if err != nil {
		return fmt.Errorf("apikeymanager: create temp: %w", err)
	}
	tmpName := tmp.Name()
	cleanup := func() { _ = os.Remove(tmpName) }

	if _, err := tmp.Write(data); err != nil {
		_ = tmp.Close()
		cleanup()
		return fmt.Errorf("apikeymanager: write temp: %w", err)
	}
	if err := tmp.Sync(); err != nil {
		_ = tmp.Close()
		cleanup()
		return fmt.Errorf("apikeymanager: fsync temp: %w", err)
	}
	if err := tmp.Close(); err != nil {
		cleanup()
		return fmt.Errorf("apikeymanager: close temp: %w", err)
	}
	// Best-effort chmod: proceed even if chmod fails (e.g. Windows).
	_ = os.Chmod(tmpName, mode)
	if err := os.Rename(tmpName, path); err != nil {
		cleanup()
		return fmt.Errorf("apikeymanager: rename temp: %w", err)
	}
	return nil
}
