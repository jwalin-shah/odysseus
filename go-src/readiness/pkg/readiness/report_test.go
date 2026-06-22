package readiness

import (
	"context"
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
	"time"
)

// stubProbe is a tiny Probe used in the DB tests. It returns the
// preconfigured error (or nil) from Ping.
type stubProbe struct{ err error }

func (s stubProbe) Ping(ctx context.Context) error { return s.err }

// ---- data_dir ------------------------------------------------------------

func TestCheck_DataDirPresent(t *testing.T) {
	dir := t.TempDir()
	rep, err := Check(context.Background(), Options{
		DataDir:       dir,
		DatabaseURL:   "sqlite:///x.db",
		Version:       "test",
		DatabaseProbe: stubProbe{},
	})
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if !rep.Ready {
		t.Fatalf("ready=false; checks=%+v", rep.Checks)
	}
	got, ok := rep.Checks["data_dir"]
	if !ok {
		t.Fatalf("data_dir check missing")
	}
	if !got.OK {
		t.Errorf("data_dir ok=false: %+v", got)
	}
	if got.Path != dir {
		t.Errorf("data_dir path=%q, want %q", got.Path, dir)
	}
}

func TestCheck_DataDirAutoMkdir(t *testing.T) {
	// base/<new>/<deeper>  — the parent chain is created.
	base := t.TempDir()
	deep := filepath.Join(base, "new", "deeper", "data")
	rep, err := Check(context.Background(), Options{
		DataDir:       deep,
		DatabaseURL:   "sqlite:///x.db",
		Version:       "test",
		DatabaseProbe: stubProbe{},
	})
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if !rep.Ready {
		t.Fatalf("ready=false after auto-mkdir; checks=%+v", rep.Checks)
	}
	if _, err := os.Stat(deep); err != nil {
		t.Fatalf("expected auto-mkdir'd dir to exist: %v", err)
	}
	if got := rep.Checks["data_dir"]; !got.OK {
		t.Errorf("data_dir ok=false: %+v", got)
	}
}

func TestCheck_DataDirEmptyPath(t *testing.T) {
	// Empty path is a hard failure — MkdirAll("") returns an
	// error on every platform.
	rep, err := Check(context.Background(), Options{
		DataDir:       "",
		DatabaseURL:   "sqlite:///x.db",
		Version:       "test",
		DatabaseProbe: stubProbe{},
	})
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if rep.Ready {
		t.Errorf("ready=true with empty dataDir; checks=%+v", rep.Checks)
	}
	got := rep.Checks["data_dir"]
	if got.OK {
		t.Errorf("data_dir ok=true with empty path: %+v", got)
	}
	if got.Error == "" {
		t.Errorf("data_dir error empty")
	}
}

func TestCheck_DataDirNotWritable(t *testing.T) {
	// Point DataDir at a path that already exists as a regular
	// file — MkdirAll on a file path returns an error, the dir is
	// never created, and the data_dir check fails.
	base := t.TempDir()
	file := filepath.Join(base, "not-a-dir")
	if err := os.WriteFile(file, []byte("not a dir"), 0o644); err != nil {
		t.Fatalf("setup: %v", err)
	}
	rep, err := Check(context.Background(), Options{
		DataDir:       file,
		DatabaseURL:   "sqlite:///x.db",
		Version:       "test",
		DatabaseProbe: stubProbe{},
	})
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if rep.Ready {
		t.Errorf("ready=true with non-dir dataDir; checks=%+v", rep.Checks)
	}
	got := rep.Checks["data_dir"]
	if got.OK {
		t.Errorf("data_dir ok=true when DataDir is a file: %+v", got)
	}
}

// ---- database ------------------------------------------------------------

func TestCheck_DatabaseOK(t *testing.T) {
	rep, err := Check(context.Background(), Options{
		DataDir:       t.TempDir(),
		DatabaseURL:   "sqlite:///x.db",
		Version:       "test",
		DatabaseProbe: stubProbe{},
	})
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if !rep.Ready {
		t.Fatalf("ready=false; checks=%+v", rep.Checks)
	}
	got, ok := rep.Checks["database"]
	if !ok || !got.OK {
		t.Errorf("database check not ok: %+v", got)
	}
}

func TestCheck_DatabaseError(t *testing.T) {
	want := errors.New("connection refused")
	rep, err := Check(context.Background(), Options{
		DataDir:       t.TempDir(),
		DatabaseURL:   "sqlite:///x.db",
		Version:       "test",
		DatabaseProbe: stubProbe{err: want},
	})
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if rep.Ready {
		t.Errorf("ready=true with failing probe; checks=%+v", rep.Checks)
	}
	got, ok := rep.Checks["database"]
	if !ok {
		t.Fatalf("database check missing")
	}
	if got.OK {
		t.Errorf("database ok=true with probe error")
	}
	if got.Error == "" {
		t.Errorf("database error string empty")
	}
	if !strings.Contains(got.Error, "connection refused") {
		t.Errorf("database error=%q does not contain underlying message", got.Error)
	}
}

func TestCheck_NilProbe(t *testing.T) {
	rep, err := Check(context.Background(), Options{
		DataDir:     t.TempDir(),
		DatabaseURL: "sqlite:///x.db",
		Version:     "test",
		// DatabaseProbe intentionally nil
	})
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if rep.Ready {
		t.Errorf("ready=true with nil probe; checks=%+v", rep.Checks)
	}
	got, ok := rep.Checks["database"]
	if !ok {
		t.Fatalf("database check missing")
	}
	if got.OK {
		t.Errorf("database ok=true with nil probe")
	}
	if got.Error != ErrNoProbe.Error() {
		t.Errorf("database error=%q, want %q", got.Error, ErrNoProbe.Error())
	}
}

func TestCheck_ProbeTimeout(t *testing.T) {
	// A probe that ignores ctx and sleeps forever — the internal
	// 2s context-with-timeout must cut it off and surface the
	// error.
	slow := ProbeFunc(func(ctx context.Context) error {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-time.After(10 * time.Second):
			return nil
		}
	})
	start := time.Now()
	rep, err := Check(context.Background(), Options{
		DataDir:       t.TempDir(),
		DatabaseURL:   "sqlite:///x.db",
		Version:       "test",
		DatabaseProbe: slow,
	})
	elapsed := time.Since(start)
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if rep.Ready {
		t.Errorf("ready=true with timed-out probe; checks=%+v", rep.Checks)
	}
	if elapsed > 4*time.Second {
		t.Errorf("probe did not honour timeout: elapsed=%s", elapsed)
	}
}

// ---- local_first ---------------------------------------------------------

func TestIsLocalFirst(t *testing.T) {
	cases := []struct {
		url  string
		want bool
	}{
		{"sqlite:///var/data/odysseus.db", true},
		{"sqlite:////absolute/path.db", true},
		{"postgresql://user:pw@localhost:5432/db", true},
		{"postgresql://user:pw@127.0.0.1:5432/db", true},
		{"mysql://localhost/db", true},
		{"postgresql://user:pw@db.internal.example.com/db", false},
		{"mysql://user:pw@10.0.0.5:3306/db", false},
		{"", false},
	}
	for _, tc := range cases {
		t.Run(tc.url, func(t *testing.T) {
			if got := IsLocalFirst(tc.url); got != tc.want {
				t.Errorf("IsLocalFirst(%q) = %v, want %v", tc.url, got, tc.want)
			}
		})
	}
}

func TestCheck_LocalFirstAlwaysOK(t *testing.T) {
	// local_first is informational — even a non-local URL must
	// record ok=true (it never fails readiness).
	rep, err := Check(context.Background(), Options{
		DataDir:       t.TempDir(),
		DatabaseURL:   "postgresql://db.example.com/x",
		Version:       "test",
		DatabaseProbe: stubProbe{},
	})
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	got, ok := rep.Checks["local_first"]
	if !ok {
		t.Fatalf("local_first check missing")
	}
	if !got.OK {
		t.Errorf("local_first ok=false; want true (informational): %+v", got)
	}
	if got.Local == nil {
		t.Errorf("local_first.Local is nil")
	} else if *got.Local {
		t.Errorf("local_first.Local = true for non-local URL")
	}
	if rep.LocalFirst {
		t.Errorf("Report.LocalFirst = true for non-local URL")
	}
}

func TestCheck_OverallReadyOnlyWhenAllPass(t *testing.T) {
	// 1) All pass.
	rep, err := Check(context.Background(), Options{
		DataDir: t.TempDir(), DatabaseURL: "sqlite:///x.db", Version: "test",
		DatabaseProbe: stubProbe{},
	})
	if err != nil {
		t.Fatalf("Check (1): %v", err)
	}
	if !rep.Ready {
		t.Errorf("scenario 1: ready=false; checks=%+v", rep.Checks)
	}

	// 2) DB fails — overall should be false even if data_dir passes.
	rep, err = Check(context.Background(), Options{
		DataDir: t.TempDir(), DatabaseURL: "sqlite:///x.db", Version: "test",
		DatabaseProbe: stubProbe{err: errors.New("boom")},
	})
	if err != nil {
		t.Fatalf("Check (2): %v", err)
	}
	if rep.Ready {
		t.Errorf("scenario 2: ready=true; checks=%+v", rep.Checks)
	}

	// 3) data_dir fails — overall should be false even if DB passes.
	rep, err = Check(context.Background(), Options{
		DataDir: "", DatabaseURL: "sqlite:///x.db", Version: "test",
		DatabaseProbe: stubProbe{},
	})
	if err != nil {
		t.Fatalf("Check (3): %v", err)
	}
	if rep.Ready {
		t.Errorf("scenario 3: ready=true; checks=%+v", rep.Checks)
	}
}

// ---- report shape --------------------------------------------------------

func TestCheck_Timestamp(t *testing.T) {
	before := time.Now().UTC().Add(-1 * time.Second)
	rep, err := Check(context.Background(), Options{
		DataDir: t.TempDir(), DatabaseURL: "sqlite:///x.db", Version: "test",
		DatabaseProbe: stubProbe{},
	})
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	after := time.Now().UTC().Add(1 * time.Second)

	ts, err := time.Parse(time.RFC3339, rep.Timestamp)
	if err != nil {
		t.Fatalf("timestamp %q is not RFC3339: %v", rep.Timestamp, err)
	}
	if ts.Before(before) || ts.After(after) {
		t.Errorf("timestamp %s not within [%s, %s]", ts, before, after)
	}
}

func TestReport_JSONShape(t *testing.T) {
	rep, err := Check(context.Background(), Options{
		DataDir: t.TempDir(), DatabaseURL: "sqlite:///x.db", Version: "test",
		DatabaseProbe: stubProbe{},
	})
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	b, err := json.Marshal(rep)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var got map[string]any
	if err := json.Unmarshal(b, &got); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	for _, k := range []string{"ready", "version", "checks", "timestamp", "local_first"} {
		if _, ok := got[k]; !ok {
			t.Errorf("missing top-level key %q in %s", k, string(b))
		}
	}
	checks, ok := got["checks"].(map[string]any)
	if !ok {
		t.Fatalf("checks not an object: %s", string(b))
	}
	for _, k := range []string{"database", "data_dir", "local_first"} {
		if _, ok := checks[k]; !ok {
			t.Errorf("missing check %q in %s", k, string(b))
		}
	}
}

func TestCheckResult_OmitEmpty(t *testing.T) {
	// local_first should serialize as {"ok": true, "local": <bool>}
	// — no "error" or "path" key.
	local := true
	cr := CheckResult{OK: true, Local: &local}
	b, err := json.Marshal(cr)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}
	var got map[string]any
	if err := json.Unmarshal(b, &got); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if _, has := got["error"]; has {
		t.Errorf("error key present in %s", string(b))
	}
	if _, has := got["path"]; has {
		t.Errorf("path key present in %s", string(b))
	}
	if !reflect.DeepEqual(got["ok"], true) {
		t.Errorf("ok=%v, want true", got["ok"])
	}
}

func TestReport_String(t *testing.T) {
	rep, err := Check(context.Background(), Options{
		DataDir: t.TempDir(), DatabaseURL: "sqlite:///x.db", Version: "test",
		DatabaseProbe: stubProbe{},
	})
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	s := rep.String()
	if !strings.Contains(s, "\"ready\"") {
		t.Errorf("String() missing ready key: %s", s)
	}
	if !strings.Contains(s, "\"local_first\"") {
		t.Errorf("String() missing local_first key: %s", s)
	}
}
