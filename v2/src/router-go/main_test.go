// Tests for the V3.1 Go port of sys_router.py.
//
// Mirrors the three pytest tests in v2/tests/test_router.py:
//   1. waterfall_claude_a        — ca available → "Routed to claude-a"
//   2. waterfall_fallback_codex  — ca+cb both <10 session → "Routed to codex"
//   3. respects_explicit_model   — --model dummy-mock → "Mock MiniMax Response"
//
// We build the actual binary once in TestMain and invoke it via exec.Command
// so the tests exercise the same CLI surface as the Python pytest suite.
package main

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

var binaryPath string

func TestMain(m *testing.M) {
	tmp, err := os.MkdirTemp("", "ody-router-test-")
	if err != nil {
		panic(err)
	}
	defer os.RemoveAll(tmp)

	binaryPath = filepath.Join(tmp, "ody-router")
	build := exec.Command("go", "build", "-o", binaryPath, ".")
	build.Dir = "."
	if out, err := build.CombinedOutput(); err != nil {
		os.Stderr.Write(out)
		panic(err)
	}

	os.Exit(m.Run())
}

// runRouter invokes the built binary with the given --model, optional extra
// env, and stdin, returning (exitCode, stdout, stderr).
func runRouter(t *testing.T, model, stdin string, extraEnv ...string) (int, string, string) {
	t.Helper()
	cmd := exec.Command(binaryPath, "--model", model)
	cmd.Env = append(os.Environ(), extraEnv...)
	cmd.Stdin = strings.NewReader(stdin)
	var stdout, stderr strings.Builder
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()
	if ee, ok := err.(*exec.ExitError); ok {
		return ee.ExitCode(), stdout.String(), stderr.String()
	}
	if err != nil {
		t.Fatalf("exec %s --model %s failed: %v\nstderr: %s", binaryPath, model, err, stderr.String())
	}
	return 0, stdout.String(), stderr.String()
}

// TestRouterWaterfallClaudeA mirrors test_router_waterfall_claude_a: with
// ca.session=50 and ca.weekly=50, the router must pick claude-a.
func TestRouterWaterfallClaudeA(t *testing.T) {
	db := t.TempDir() + "/quota-live.json"
	data := map[string]any{
		"providers": map[string]any{
			"ca": map[string]any{
				"quotas": map[string]any{
					"session_pct_remaining": 50,
					"weekly_pct_remaining":  50,
				},
			},
		},
	}
	b, _ := json.Marshal(data)
	if err := os.WriteFile(db, b, 0o644); err != nil {
		t.Fatalf("write quota file: %v", err)
	}

	exit, stdout, stderr := runRouter(t, "auto", "Write my resume", "SYS_QUOTA_STATE="+db)
	if exit != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%s)", exit, stderr)
	}
	if !strings.Contains(stdout, "Routed to claude-a successfully") {
		t.Fatalf("expected 'Routed to claude-a successfully' in stdout, got: %q", stdout)
	}
}

// TestRouterWaterfallFallbackCodex mirrors test_router_waterfall_fallback_codex:
// with ca and cb both at session=5 (<10), the router must fall through to codex.
func TestRouterWaterfallFallbackCodex(t *testing.T) {
	db := t.TempDir() + "/quota-live.json"
	data := map[string]any{
		"providers": map[string]any{
			"ca": map[string]any{
				"quotas": map[string]any{
					"session_pct_remaining": 5,
					"weekly_pct_remaining":  50,
				},
			},
			"cb": map[string]any{
				"quotas": map[string]any{
					"session_pct_remaining": 5,
					"weekly_pct_remaining":  50,
				},
			},
		},
	}
	b, _ := json.Marshal(data)
	if err := os.WriteFile(db, b, 0o644); err != nil {
		t.Fatalf("write quota file: %v", err)
	}

	exit, stdout, stderr := runRouter(t, "auto", "Test Prompt", "SYS_QUOTA_STATE="+db)
	if exit != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%s)", exit, stderr)
	}
	if !strings.Contains(stdout, "Routed to codex successfully") {
		t.Fatalf("expected 'Routed to codex successfully' in stdout, got: %q", stdout)
	}
}

// TestRouterRespectsExplicitModel mirrors test_router_respects_explicit_model:
// --model dummy-mock must short-circuit to the mock response, ignoring any
// quota state (so we don't set SYS_QUOTA_STATE here, matching the pytest).
func TestRouterRespectsExplicitModel(t *testing.T) {
	exit, stdout, stderr := runRouter(t, "dummy-mock", "Test Prompt")
	if exit != 0 {
		t.Fatalf("expected exit 0, got %d (stderr=%s)", exit, stderr)
	}
	if !strings.Contains(stdout, "Mock MiniMax Response") {
		t.Fatalf("expected 'Mock MiniMax Response' in stdout, got: %q", stdout)
	}
}
