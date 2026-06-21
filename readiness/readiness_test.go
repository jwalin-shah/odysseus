package readiness

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

// allPass returns a Config wired for the happy path: a no-op DB probe
// and a temp data dir.
func allPass(t *testing.T) Config {
	t.Helper()
	return Config{
		AppVersion:  "1.2.3",
		DataDir:     t.TempDir(),
		DatabaseURL: "sqlite:///./test.db",
		DBProbe:     func(ctx context.Context) error { return nil },
	}
}

func TestRun_AllChecksPass(t *testing.T) {
	cfg := allPass(t)
	cfg.DatabaseURL = "sqlite:///./test.db"

	r := Run(context.Background(), cfg)
	if !r.Ready {
		t.Fatalf("expected ready=true, got %+v", r)
	}
	if r.Version != "1.2.3" {
		t.Errorf("Version = %q, want %q", r.Version, "1.2.3")
	}
	if got, want := len(r.Checks), 3; got != want {
		t.Fatalf("len(Checks) = %d, want %d", got, want)
	}
	wantNames := map[string]bool{"database": false, "data_dir": false, "local_first": false}
	for _, c := range r.Checks {
		if _, ok := wantNames[c.Name]; !ok {
			t.Errorf("unexpected check name %q", c.Name)
		}
		wantNames[c.Name] = true
		if !c.OK {
			t.Errorf("check %q ok=false, want true (err=%q)", c.Name, c.Error)
		}
	}
	for name, seen := range wantNames {
		if !seen {
			t.Errorf("missing check %q", name)
		}
	}
	if r.Timestamp.Location() != time.UTC {
		t.Errorf("Timestamp not in UTC: %v", r.Timestamp.Location())
	}
}

func TestRun_DatabaseFailure(t *testing.T) {
	cfg := allPass(t)
	cfg.DBProbe = func(ctx context.Context) error { return errors.New("boom") }

	r := Run(context.Background(), cfg)
	if r.Ready {
		t.Fatalf("expected ready=false on db failure")
	}
	if r.Checks[0].Name != "database" || r.Checks[0].OK {
		t.Fatalf("database check should fail: %+v", r.Checks[0])
	}
	if r.Checks[0].Error != "boom" {
		t.Errorf("Error = %q, want %q", r.Checks[0].Error, "boom")
	}
}

func TestRun_DatabaseProbeUnset(t *testing.T) {
	cfg := allPass(t)
	cfg.DBProbe = nil

	r := Run(context.Background(), cfg)
	if r.Ready {
		t.Fatalf("expected ready=false when no DB probe registered")
	}
	if r.Checks[0].Error == "" {
		t.Errorf("expected an error message on unset probe")
	}
}

func TestRun_DataDirFailure(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("/dev/null semantics differ on Windows")
	}
	cfg := allPass(t)
	// /dev/null is a file, not a directory — MkdirAll will refuse to
	// create a child path inside it.
	cfg.DataDir = "/dev/null/subdir"

	r := Run(context.Background(), cfg)
	if r.Ready {
		t.Fatalf("expected ready=false on data_dir failure")
	}
	if r.Checks[1].Name != "data_dir" || r.Checks[1].OK {
		t.Fatalf("data_dir check should fail: %+v", r.Checks[1])
	}
	if r.Checks[1].Error == "" {
		t.Errorf("expected an error message on data_dir failure")
	}
}

func TestRun_DataDirCreatedIfMissing(t *testing.T) {
	parent := t.TempDir()
	nested := filepath.Join(parent, "fresh", "deeper")
	cfg := allPass(t)
	cfg.DataDir = nested

	if _, err := os.Stat(nested); !os.IsNotExist(err) {
		t.Fatalf("precondition: nested path should not exist; stat err=%v", err)
	}

	r := Run(context.Background(), cfg)
	if !r.Ready {
		t.Fatalf("expected ready=true after auto-mkdir: %+v", r)
	}
	info, err := os.Stat(nested)
	if err != nil || !info.IsDir() {
		t.Fatalf("expected nested dir to be created: err=%v isDir=%v", err, info != nil && info.IsDir())
	}
}

func TestRun_DataDirProbeNaming(t *testing.T) {
	parent := t.TempDir()
	cfg := allPass(t)
	cfg.DataDir = parent

	r := Run(context.Background(), cfg)
	if !r.Ready {
		t.Fatalf("expected ready=true: %+v", r)
	}
	// No probe file should remain after Run.
	entries, err := os.ReadDir(parent)
	if err != nil {
		t.Fatalf("ReadDir: %v", err)
	}
	for _, e := range entries {
		if strings.HasPrefix(e.Name(), ".ready_probe_") {
			t.Errorf("probe file %q should have been removed", e.Name())
		}
	}
}

func TestIsLocal(t *testing.T) {
	cases := []struct {
		url  string
		want bool
	}{
		{"sqlite:///foo", true},
		{"sqlite:foo", true},
		{"postgresql://localhost/foo", true},
		{"postgresql://user:pw@localhost:5432/db", true},
		{"postgresql://127.0.0.1/foo", true},
		{"postgresql://db.example.com/foo", false},
		{"mysql://db.example.com/foo", false},
		{"", false},
	}
	for _, tc := range cases {
		t.Run(tc.url, func(t *testing.T) {
			if got := isLocal(tc.url); got != tc.want {
				t.Errorf("isLocal(%q) = %v, want %v", tc.url, got, tc.want)
			}
		})
	}
}

func TestRun_LocalFirstVariants(t *testing.T) {
	cases := []struct {
		name string
		url  string
		want bool
	}{
		{"sqlite_three_slash", "sqlite:///foo", true},
		{"sqlite_no_slash", "sqlite:foo", true},
		{"postgres_localhost", "postgresql://localhost/foo", true},
		{"postgres_loopback_ip", "postgresql://127.0.0.1/foo", true},
		{"postgres_remote", "postgresql://db.example.com/foo", false},
		{"empty", "", false},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			cfg := allPass(t)
			cfg.DatabaseURL = tc.url
			r := Run(context.Background(), cfg)
			if r.Checks[2].Name != "local_first" {
				t.Fatalf("expected local_first check at index 2: %+v", r.Checks[2])
			}
			if !r.Checks[2].OK {
				t.Errorf("local_first must always report ok=true; got %+v", r.Checks[2])
			}
			got := false
			if v, ok := r.Checks[2].Details["local"].(bool); ok {
				got = v
			}
			if got != tc.want {
				t.Errorf("local = %v, want %v", got, tc.want)
			}
		})
	}
}

func TestRun_LocalFirstAlwaysOk(t *testing.T) {
	// Even with a remote URL the local_first check must not fail the
	// report — it's informational, matching the Python behavior.
	cfg := allPass(t)
	cfg.DatabaseURL = "postgresql://db.example.com/foo"

	r := Run(context.Background(), cfg)
	if !r.Ready {
		t.Fatalf("remote URL must not fail readiness: %+v", r)
	}
}

func TestReport_JSONShape(t *testing.T) {
	cfg := allPass(t)
	r := Run(context.Background(), cfg)
	b, err := json.Marshal(&r)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var raw map[string]any
	if err := json.Unmarshal(b, &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	for _, k := range []string{"ready", "version", "checks", "timestamp"} {
		if _, ok := raw[k]; !ok {
			t.Errorf("missing top-level key %q in %s", k, string(b))
		}
	}
	if _, ok := raw["timestamp"].(string); !ok {
		t.Errorf("timestamp should be a string: %v", raw["timestamp"])
	}
	// ready should be a bool.
	if _, ok := raw["ready"].(bool); !ok {
		t.Errorf("ready should be a bool: %v", raw["ready"])
	}
}

func TestCheck_JSONShape(t *testing.T) {
	cfg := allPass(t)
	r := Run(context.Background(), cfg)
	b, err := json.Marshal(&r)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var raw struct {
		Checks []map[string]any `json:"checks"`
	}
	if err := json.Unmarshal(b, &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	byName := map[string]map[string]any{}
	for _, c := range raw.Checks {
		name, _ := c["name"].(string)
		// Name field is hidden by json:"-" so it should NOT appear in
		// the marshaled output (the Python output also has no name
		// key, only the check body).
		if _, hasName := c["name"]; hasName {
			byName[name] = c
		}
		// Use the raw check body keyed by its order to find data_dir.
		_ = byName
	}
	// Re-decode with a more permissive shape so we can inspect by index.
	var perm struct {
		Checks []map[string]any `json:"checks"`
	}
	if err := json.Unmarshal(b, &perm); err != nil {
		t.Fatalf("unmarshal2: %v", err)
	}
	if len(perm.Checks) != 3 {
		t.Fatalf("expected 3 checks, got %d", len(perm.Checks))
	}
	// database — should only have ok:true
	db := perm.Checks[0]
	if db["ok"] != true {
		t.Errorf("database.ok = %v, want true", db["ok"])
	}
	if _, has := db["error"]; has {
		t.Errorf("database should not carry an error key: %+v", db)
	}
	if _, has := db["path"]; has {
		t.Errorf("database should not carry a path key: %+v", db)
	}
	// data_dir — should have ok:true and path
	dd := perm.Checks[1]
	if dd["ok"] != true {
		t.Errorf("data_dir.ok = %v, want true", dd["ok"])
	}
	if dd["path"] == nil {
		t.Errorf("data_dir.path missing: %+v", dd)
	}
	if _, has := dd["error"]; has {
		t.Errorf("data_dir should not carry an error key: %+v", dd)
	}
	// local_first — should have ok:true and local
	lf := perm.Checks[2]
	if lf["ok"] != true {
		t.Errorf("local_first.ok = %v, want true", lf["ok"])
	}
	if _, has := lf["local"]; !has {
		t.Errorf("local_first.local missing: %+v", lf)
	}
}

func TestCheck_JSONErrorOnlyOnFailure(t *testing.T) {
	cfg := allPass(t)
	cfg.DBProbe = func(ctx context.Context) error { return errors.New("dial tcp: refused") }
	r := Run(context.Background(), cfg)
	b, err := json.Marshal(&r)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var raw struct {
		Checks []map[string]any `json:"checks"`
	}
	if err := json.Unmarshal(b, &raw); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	db := raw.Checks[0]
	if db["ok"] != false {
		t.Errorf("database.ok = %v, want false", db["ok"])
	}
	if got, _ := db["error"].(string); got != "dial tcp: refused" {
		t.Errorf("database.error = %v, want %q", db["error"], "dial tcp: refused")
	}
}

func TestRun_TimestampUTC(t *testing.T) {
	cfg := allPass(t)
	before := time.Now().UTC().Add(-time.Second)
	r := Run(context.Background(), cfg)
	after := time.Now().UTC().Add(time.Second)

	if r.Timestamp.Location() != time.UTC {
		t.Errorf("timestamp location = %v, want UTC", r.Timestamp.Location())
	}
	if r.Timestamp.Before(before) || r.Timestamp.After(after) {
		t.Errorf("timestamp %v outside [%v, %v]", r.Timestamp, before, after)
	}
	// And confirm the JSON form is RFC3339 / ISO 8601.
	b, err := json.Marshal(&r)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var raw map[string]any
	_ = json.Unmarshal(b, &raw)
	ts, _ := raw["timestamp"].(string)
	parsed, err := time.Parse(time.RFC3339Nano, ts)
	if err != nil {
		// Fall back to RFC3339 if no nanos were emitted.
		parsed, err = time.Parse(time.RFC3339, ts)
	}
	if err != nil {
		t.Errorf("timestamp %q is not RFC3339: %v", ts, err)
	}
	if parsed.Location() != time.UTC {
		t.Errorf("parsed timestamp not UTC: %v", parsed.Location())
	}
}

func TestRun_RespectsContextCancellation(t *testing.T) {
	cfg := allPass(t)
	// Probe that only returns once the context is done. This lets us
	// observe the cancellation behavior of Run.
	cfg.DBProbe = func(ctx context.Context) error {
		<-ctx.Done()
		return ctx.Err()
	}
	cfg.DataDir = "/dev/null/blocked" // never reached, but ensures we'd block on dir check if we got there

	ctx, cancel := context.WithCancel(context.Background())
	done := make(chan readinessReport, 1)
	go func() {
		done <- Run(ctx, cfg)
	}()
	cancel()

	select {
	case r := <-done:
		if r.Ready {
			t.Fatalf("expected ready=false after cancel")
		}
		// The DB probe should have surfaced ctx.Err(); either that or
		// the data_dir check may be the failing one — both are valid
		// outcomes as long as Ready is false.
		if r.Checks[0].OK {
			t.Errorf("database check should not be ok after cancel")
		}
	case <-time.After(2 * time.Second):
		t.Fatal("Run did not return within 2s of context cancellation")
	}
}

// readinessReport is a local alias used only in the cancellation test
// to avoid importing the Report type into a separate variable.
type readinessReport = Report

func TestPingDB_NoDriver(t *testing.T) {
	cases := []struct {
		url     string
		wantSub string
	}{
		{"sqlite:///foo", "sqlite driver not registered"},
		{"file:./foo.db", "sqlite driver not registered"},
		{"postgresql://localhost/foo", "postgres driver not registered"},
		{"mysql://db.example.com/foo", "unsupported database scheme"},
	}
	for _, tc := range cases {
		t.Run(tc.url, func(t *testing.T) {
			err := PingDB(context.Background(), tc.url)
			if err == nil {
				t.Fatalf("expected error for %q", tc.url)
			}
			if !strings.Contains(err.Error(), tc.wantSub) {
				t.Errorf("PingDB(%q) = %q, want substring %q", tc.url, err.Error(), tc.wantSub)
			}
		})
	}
}
