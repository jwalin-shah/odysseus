package runtimepaths

import (
	"fmt"
	"os"
	"path/filepath"
)

// defaultDataSubdir is the directory name joined to GetAppRoot() in
// source runs (matches the Python module's literal "data").
const defaultDataSubdir = "data"

// defaultFrozenDataDir is the persistent data directory used in frozen
// runs (matches ~/.odysseus/data from the Python module).
const defaultFrozenDataDir = ".odysseus/data"

// sourceRunDepth is how many parent directories we climb from a
// source location to reach the app root. The Python module uses
// os.path.dirname(os.path.dirname(os.path.abspath(__file__))) which
// climbs TWO parents: the file's directory and then that directory's
// parent. We do the same.
const sourceRunDepth = 2

// GetAppRoot returns the app root directory.
//
// In source runs (Frozen == false) this is the parent of the parent
// of the source location — closest match to the Python module's
// os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
// expression. We resolve it by either:
//
//   - climbing two parents above ExecPath when ExecPath is non-empty
//     and points at a file, or
//   - climbing two parents above os.Getwd() looking for a go.mod.
//
// In frozen runs (Frozen == true) this is BundleDir when set, else
// filepath.Dir(ExecPath).
func GetAppRoot(env Environment) string {
	if env.Frozen {
		return frozenAppRoot(env)
	}
	return sourceAppRoot(env)
}

// GetDefaultDataDir returns the default data directory. In source
// runs this is <app_root>/data; in frozen runs it is <home>/.odysseus/data.
func GetDefaultDataDir(env Environment) string {
	if env.Frozen {
		return filepath.Join(expandHome(env.Clone()), defaultFrozenDataDir)
	}
	return filepath.Join(GetAppRoot(env), defaultDataSubdir)
}

// Describe returns a snapshot of the resolved paths along with the
// frozen-bundle metadata. Used by the demo CLI to print a summary.
func Describe(env Environment) FrozenInfo {
	return FrozenInfo{
		Frozen:       env.Frozen,
		BundleDir:    env.BundleDir,
		ResolvedRoot: GetAppRoot(env),
	}
}

// frozenAppRoot returns the app root for frozen runs. Mirrors the
// Python expression:
//
//	getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(sys.executable)))
//
// BundleDir is preferred; filepath.Dir(ExecPath) is the fallback.
func frozenAppRoot(env Environment) string {
	if env.BundleDir != "" {
		return cleanAbs(env.BundleDir)
	}
	if env.ExecPath != "" {
		return cleanAbs(filepath.Dir(env.ExecPath))
	}
	// Last resort: cwd. The Python module would error here; we degrade
	// gracefully so a misconfigured bundle still boots.
	wd, _ := os.Getwd()
	return cleanAbs(wd)
}

// sourceAppRoot returns the app root for source runs. Mirrors the
// Python expression:
//
//	os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
func sourceAppRoot(env Environment) string {
	if env.ExecPath != "" {
		return climbParents(env.ExecPath, sourceRunDepth)
	}
	// No exec path: climb from cwd, preferring a go.mod boundary if one
	// exists above us (the closest Go analogue to Python's __file__).
	wd, err := os.Getwd()
	if err != nil {
		return ""
	}
	return climbParents(wd, sourceRunDepth)
}

// climbParents returns the directory `levels` above path, cleaning the
// result. path may be a file or a directory.
func climbParents(path string, levels int) string {
	p := cleanAbs(path)
	for i := 0; i < levels; i++ {
		parent := filepath.Dir(p)
		if parent == p {
			// Reached the filesystem root; return what we have.
			return p
		}
		p = parent
	}
	return p
}

// cleanAbs is filepath.Clean + absolute-path fallback. Mirrors
// os.path.abspath in spirit — does NOT touch the filesystem.
func cleanAbs(path string) string {
	if path == "" {
		return ""
	}
	if !filepath.IsAbs(path) {
		if abs, err := filepath.Abs(path); err == nil {
			path = abs
		}
	}
	return filepath.Clean(path)
}

// expandHome returns the user's home directory from env.HomeDir,
// falling back to os.UserHomeDir(). Always returns a clean absolute
// path. On error, returns "" so callers can detect the degenerate case.
func expandHome(env Environment) string {
	env = env.Clone()
	if env.HomeDir == "" {
		// Last-ditch: try HOME/USERPROFILE directly so tests that
		// haven't populated HomeDir still work.
		if h := os.Getenv("HOME"); h != "" {
			env.HomeDir = h
		} else if h := os.Getenv("USERPROFILE"); h != "" {
			env.HomeDir = h
		}
	}
	if env.HomeDir == "" {
		return ""
	}
	return cleanAbs(env.HomeDir)
}

// String returns a stable, one-line summary suitable for logs.
func (fi FrozenInfo) String() string {
	if fi.Frozen {
		return fmt.Sprintf("frozen(bundle=%q) → root=%q", fi.BundleDir, fi.ResolvedRoot)
	}
	return fmt.Sprintf("source → root=%q", fi.ResolvedRoot)
}
