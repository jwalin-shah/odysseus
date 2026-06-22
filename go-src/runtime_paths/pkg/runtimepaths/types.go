// Package runtimepaths resolves the runtime paths used everywhere else
// in the application. It is the Go port of src/runtime_paths.py.
//
// Two paths are exposed:
//
//   - GetAppRoot — the directory the process treats as its top-level
//     workspace (the repo root in source runs, the bundle content root
//     in frozen runs).
//   - GetDefaultDataDir — the directory persistent state is written to
//     (<app_root>/data in source runs, ~/.odysseus/data in frozen runs).
//
// The Environment struct is the caller's way to describe the runtime
// (frozen? bundle dir? executable path? user home?). Tests can populate
// it directly to drive every branch deterministically.
package runtimepaths

import "os"

// Environment describes the runtime context for path resolution.
//
// A zero value is intentionally usable: GetAppRoot will fall back to
// os.Getwd and GetDefaultDataDir will call os.UserHomeDir when HomeDir
// is empty.
type Environment struct {
	// Frozen is true when the process is running from a packaged bundle
	// (PyInstaller analogue: sys.frozen). When true, GetAppRoot returns
	// BundleDir (or filepath.Dir(ExecPath) if BundleDir is empty) and
	// GetDefaultDataDir returns <HomeDir>/.odysseus/data.
	Frozen bool

	// BundleDir is the content root of a frozen bundle (PyInstaller's
	// _MEIPASS analogue). Only consulted when Frozen is true. May be
	// empty — the resolver falls back to filepath.Dir(ExecPath).
	BundleDir string

	// ExecPath is the path of the running executable. Used in two
	// places: (a) as a frozen-bundle fallback when BundleDir is empty,
	// and (b) as the source-run root when no go.mod is found above the
	// cwd. Mirrors sys.executable.
	ExecPath string

	// HomeDir is the user's home directory. When empty, the resolver
	// calls os.UserHomeDir() and caches the result on the returned
	// Environment. Mirrors os.path.expanduser("~").
	HomeDir string
}

// Clone returns a deep-ish copy of env with HomeDir filled in if it
// was empty. The resolver uses this to avoid surprising the caller by
// mutating their Environment across calls.
func (e Environment) Clone() Environment {
	if e.HomeDir == "" {
		if h, err := os.UserHomeDir(); err == nil {
			e.HomeDir = h
		}
	}
	return e
}

// FrozenInfo summarises the frozen-bundle state used by GetAppRoot.
// It is exported primarily for the demo CLI; tests use it to assert
// which branch of the resolver fired.
type FrozenInfo struct {
	// Frozen mirrors Environment.Frozen.
	Frozen bool
	// BundleDir mirrors Environment.BundleDir (may be empty).
	BundleDir string
	// ResolvedRoot is what GetAppRoot returned for this Environment.
	ResolvedRoot string
}
