package runtimepaths

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// IsBundle reports whether the given path looks like a frozen bundle
// content root. The heuristic is intentionally conservative — it
// returns true only when the path exists, is a directory, and contains
// at least one of the well-known bundle markers.
//
// This is the only piece of the port that touches the filesystem to
// "discover" state; the resolver itself never reads disk.
func IsBundle(path string) bool {
	if path == "" {
		return false
	}
	fi, err := os.Stat(path)
	if err != nil || !fi.IsDir() {
		return false
	}
	for _, marker := range bundleMarkers() {
		if _, err := os.Stat(filepath.Join(path, marker)); err == nil {
			return true
		}
	}
	return false
}

// bundleMarkers lists files that almost always live in a frozen bundle
// content root. PyInstaller's _MEIPASS typically contains the bundled
// binaries plus a `PYZ-00.pyz` archive; we keep it simple.
func bundleMarkers() []string {
	return []string{
		"PYZ-00.pyz",
		"struct.dat",
		"base_library.zip",
	}
}

// FrozenProbe executes a small command to detect whether the running
// binary appears to be inside a bundle. The Python module relies on
// `sys.frozen` which is set by PyInstaller; in Go we have no such
// flag, so we look at argv[0] and the filesystem above it.
//
// This function deliberately uses os/exec to inspect the runtime
// platform; tests bypass it via Environment.Frozen directly.
func FrozenProbe() (bool, string, error) {
	exe, err := os.Executable()
	if err != nil {
		return false, "", fmt.Errorf("runtimepaths: locate executable: %w", err)
	}
	dir := filepath.Dir(exe)
	// Walk up two parents (matching the Python module's depth). The
	// bundle content root is typically that high.
	for i := 0; i < 2; i++ {
		if IsBundle(dir) {
			return true, dir, nil
		}
		parent := filepath.Dir(dir)
		if parent == dir {
			break
		}
		dir = parent
	}
	return false, "", nil
}

// ExpandUser is the runtime-paths equivalent of os.path.expanduser("~").
// It returns path unchanged if it does not begin with "~". Otherwise it
// expands the leading "~" or "~user" segment against env.HomeDir.
func ExpandUser(env Environment, path string) string {
	if path == "" || path[0] != '~' {
		return path
	}
	home := expandHome(env)
	if home == "" {
		return path
	}
	// "~" or "~/..."
	if path == "~" || strings.HasPrefix(path, "~/") || strings.HasPrefix(path, "~\\") {
		return filepath.Join(home, path[1:])
	}
	// "~user/..." is not supported on this port — the Python module
	// also does not support it (it calls os.path.expanduser which
	// resolves ~user via pwd lookup, which we don't replicate here).
	return path
}
