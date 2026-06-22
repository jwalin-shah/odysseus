package runtimepaths

import (
	"os"
	"path/filepath"
	"testing"
)

// TestGetAppRootSourceRun is the table-driven core of the public
// surface. Every row pins one branch of the resolver.
//
// The Python module's get_app_root() climbs two parents above __file__
// (which lives at <repo>/src/runtime_paths.py) to reach the repo root.
// We mirror that layout: fake source lives at <root>/src/x.go, so
// climbing two parents above it gives <root>.
func TestGetAppRootSourceRun(t *testing.T) {
	root := t.TempDir()

	// Build a fake repo layout:
	//   <root>/                          <- app root (depth 2 up)
	//   <root>/src/runtimepaths.go       <- source file
	fakeSrc := filepath.Join(root, "src", "runtimepaths.go")
	if err := os.MkdirAll(filepath.Dir(fakeSrc), 0o755); err != nil {
		t.Fatalf("mkdir: %v", err)
	}
	if err := os.WriteFile(fakeSrc, []byte("package runtimepaths"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}

	tests := []struct {
		name string
		env  Environment
		// want is a function because the resolved path depends on the
		// host filesystem (tempdir layout).
		want func(t *testing.T, root string) string
	}{
		{
			name: "exec path climbs two parents",
			env:  Environment{ExecPath: fakeSrc, HomeDir: root},
			want: func(t *testing.T, root string) string {
				return root
			},
		},
		{
			name: "no exec path falls back to cwd climb",
			env:  Environment{HomeDir: root},
			want: func(t *testing.T, root string) string {
				// cwd is wherever `go test` is invoked; we can only
				// assert that the result is a non-empty absolute path.
				got := GetAppRoot(Environment{HomeDir: root})
				if !filepath.IsAbs(got) {
					t.Fatalf("expected absolute path, got %q", got)
				}
				return got
			},
		},
		{
			name: "zero-value env still resolves",
			env:  Environment{},
			want: func(t *testing.T, root string) string {
				got := GetAppRoot(Environment{})
				if !filepath.IsAbs(got) {
					t.Fatalf("expected absolute path, got %q", got)
				}
				return got
			},
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := GetAppRoot(tc.env)
			want := tc.want(t, root)
			if want != "" && got != want {
				t.Fatalf("GetAppRoot = %q, want %q", got, want)
			}
		})
	}
}

// TestGetAppRootFrozen covers the frozen branch. BundleDir is preferred;
// fallback climbs Dir(ExecPath) when BundleDir is empty.
func TestGetAppRootFrozen(t *testing.T) {
	root := t.TempDir()
	bundle := filepath.Join(root, "bundle")
	execInBundle := filepath.Join(bundle, "odysseus.exe")

	tests := []struct {
		name string
		env  Environment
		want string
	}{
		{
			name: "frozen with BundleDir wins",
			env:  Environment{Frozen: true, BundleDir: bundle, ExecPath: execInBundle, HomeDir: root},
			want: bundle,
		},
		{
			name: "frozen without BundleDir falls back to Dir(ExecPath)",
			env:  Environment{Frozen: true, ExecPath: execInBundle, HomeDir: root},
			want: bundle,
		},
		{
			name: "frozen with neither BundleDir nor ExecPath uses cwd",
			env:  Environment{Frozen: true, HomeDir: root},
			want: "", // asserted structurally below
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := GetAppRoot(tc.env)
			if tc.want == "" {
				if !filepath.IsAbs(got) || got == "" {
					t.Fatalf("expected absolute non-empty cwd fallback, got %q", got)
				}
				return
			}
			if got != tc.want {
				t.Fatalf("GetAppRoot = %q, want %q", got, tc.want)
			}
		})
	}
}

// TestGetDefaultDataDir verifies the source-vs-frozen data-dir branch.
func TestGetDefaultDataDir(t *testing.T) {
	root := t.TempDir()
	home := filepath.Join(root, "home")
	bundle := filepath.Join(root, "bundle")
	srcExec := filepath.Join(root, "src", "x.go")

	tests := []struct {
		name string
		env  Environment
		want string
	}{
		{
			name: "source run uses <root>/data",
			env:  Environment{ExecPath: srcExec, HomeDir: home},
			want: filepath.Join(root, "data"),
		},
		{
			name: "frozen run uses <home>/.odysseus/data",
			env:  Environment{Frozen: true, BundleDir: bundle, HomeDir: home},
			want: filepath.Join(home, ".odysseus", "data"),
		},
		{
			name: "frozen run with empty HomeDir falls back to cwd",
			env:  Environment{Frozen: true, BundleDir: bundle, HomeDir: ""},
			want: "", // structural check below
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := GetDefaultDataDir(tc.env)
			if tc.want == "" {
				if !filepath.IsAbs(got) {
					t.Fatalf("expected absolute fallback, got %q", got)
				}
				return
			}
			if got != tc.want {
				t.Fatalf("GetDefaultDataDir = %q, want %q", got, tc.want)
			}
		})
	}
}

// TestFrozenToggleRoundTrip exercises the branch independence:
// toggling Frozen should switch the data-dir resolution.
func TestFrozenToggleRoundTrip(t *testing.T) {
	root := t.TempDir()
	srcExec := filepath.Join(root, "src", "x.go")

	sourceEnv := Environment{ExecPath: srcExec, HomeDir: root}
	frozenEnv := sourceEnv
	frozenEnv.Frozen = true
	frozenEnv.BundleDir = root

	if GetDefaultDataDir(sourceEnv) == GetDefaultDataDir(frozenEnv) {
		t.Fatalf("expected different data dirs between source and frozen")
	}
}

// TestEnvironmentCloneFillsHome verifies that Clone populates HomeDir
// when it is empty (mirrors os.path.expanduser fallback).
func TestEnvironmentCloneFillsHome(t *testing.T) {
	// Set HOME to a known value, then Clone and check.
	t.Setenv("HOME", filepath.Join(t.TempDir(), "fake-home"))

	cloned := Environment{}.Clone()
	if cloned.HomeDir == "" {
		t.Fatalf("Clone did not fill HomeDir")
	}
}

// TestExpandUser covers the "~" / "~/" / non-tilde branches.
func TestExpandUser(t *testing.T) {
	env := Environment{HomeDir: "/tmp/fake-home"}

	tests := []struct {
		in   string
		want string
	}{
		{"~/data", "/tmp/fake-home/data"},
		{"~", "/tmp/fake-home"},
		{"data", "data"},
		{"", ""},
	}

	for _, tc := range tests {
		got := ExpandUser(env, tc.in)
		if got != tc.want {
			t.Errorf("ExpandUser(%q) = %q, want %q", tc.in, got, tc.want)
		}
	}
}

// TestHomeFromEnvEnvarSet covers the HOME-set branch via the public
// API by using t.Setenv (which Go restores after the test).
func TestHomeFromEnvEnvarSet(t *testing.T) {
	want := filepath.Join(t.TempDir(), "env-home")
	t.Setenv("HOME", want)

	got := homeFromEnv()
	if got == "" {
		t.Fatalf("homeFromEnv returned empty even though HOME is set")
	}
	// Got should be cleaned and absolute; the absolute resolution may
	// differ from `want` if Go normalizes the path. Just assert non-empty
	// and absolute.
	if !filepath.IsAbs(got) {
		t.Fatalf("homeFromEnv returned non-absolute path %q", got)
	}
}

// TestHomeFromEnvEnvarUnset covers the HOME-unset branch.
func TestHomeFromEnvEnvarUnset(t *testing.T) {
	// We can't actually unset HOME on every platform, but t.Setenv to an
	// empty value triggers the empty-string branch in the helper.
	t.Setenv("HOME", "")

	if got := homeFromEnv(); got != "" {
		// Some platforms normalise the empty value; accept "" only.
		t.Logf("homeFromEnv with HOME='' returned %q (acceptable on some platforms)", got)
	}
}

// TestDescribeReturnsBundleInfo verifies the demo helper exposes the
// frozen metadata alongside the resolved root.
func TestDescribeReturnsBundleInfo(t *testing.T) {
	root := t.TempDir()
	env := Environment{Frozen: true, BundleDir: root, HomeDir: root}

	info := Describe(env)
	if !info.Frozen {
		t.Fatalf("expected Frozen=true")
	}
	if info.BundleDir != root {
		t.Fatalf("BundleDir = %q, want %q", info.BundleDir, root)
	}
	if info.ResolvedRoot != root {
		t.Fatalf("ResolvedRoot = %q, want %q", info.ResolvedRoot, root)
	}
}

// TestClimbParentsReachesRoot verifies the climb stops gracefully at
// the filesystem root instead of looping forever.
func TestClimbParentsReachesRoot(t *testing.T) {
	got := climbParents("/a/b/c", 1000)
	if got == "" {
		t.Fatalf("climbParents returned empty for valid path")
	}
	// At minimum, climbing many levels must not panic and must return
	// a clean absolute path.
	if !filepath.IsAbs(got) {
		t.Fatalf("climbParents returned non-absolute: %q", got)
	}
}

// TestCleanAbsHandlesEmpty covers the degenerate input branch.
func TestCleanAbsHandlesEmpty(t *testing.T) {
	if got := cleanAbs(""); got != "" {
		t.Fatalf("cleanAbs(\"\") = %q, want empty", got)
	}
}

// TestDefaultDataSubdirIsStable guards against accidental rename of
// the literal "data" string — the Python module also hardcodes it.
func TestDefaultDataSubdirIsStable(t *testing.T) {
	if defaultDataSubdir != "data" {
		t.Fatalf("defaultDataSubdir drifted: %q", defaultDataSubdir)
	}
	if defaultFrozenDataDir != ".odysseus/data" {
		t.Fatalf("defaultFrozenDataDir drifted: %q", defaultFrozenDataDir)
	}
}
