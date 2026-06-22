package readiness

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Options configures a single Check call.
//
// Zero value is NOT meaningful for most fields — callers should always
// supply at least DataDir and DatabaseURL. The only field with a
// meaningful zero default is DatabaseProbe, which is treated as a
// no-op probe when nil.
type Options struct {
	// DataDir is the path probe target. Missing directories are
	// auto-created (mirroring os.makedirs(..., exist_ok=True) in the
	// Python source).
	DataDir string

	// DatabaseURL is used only by the local_first heuristic. The
	// package never opens the URL itself; the DB check goes through
	// the injected Probe.
	DatabaseURL string

	// Version is recorded verbatim on the report. If empty, the
	// report carries an empty string (matching the Python source,
	// which uses APP_VERSION from core.constants).
	Version string

	// DatabaseProbe is an optional DB ping. When nil, the database
	// check is recorded as {"ok": false, "error": "no probe
	// configured"}.
	DatabaseProbe Probe
}

// Report is the top-level JSON-serialisable report.
//
//	{
//	  "ready":      true,
//	  "version":    "0.0.0-demo",
//	  "checks":     {...},
//	  "timestamp":  "2026-06-21T12:34:56Z",
//	  "local_first": true
//	}
type Report struct {
	Ready      bool                   `json:"ready"`
	Version    string                 `json:"version"`
	Checks     map[string]CheckResult `json:"checks"`
	Timestamp  string                 `json:"timestamp"`
	LocalFirst bool                   `json:"local_first"`
}

// CheckResult is one entry in the report's Checks map. The JSON
// shape mirrors the Python dict exactly: only the fields relevant to
// each check are populated, the rest are omitted.
//
//   - database:    {ok, error?}
//   - data_dir:    {ok, path, error?}
//   - local_first: {ok, local}
type CheckResult struct {
	OK    bool   `json:"ok"`
	Error string `json:"error,omitempty"`
	Path  string `json:"path,omitempty"`
	Local *bool  `json:"local,omitempty"`
}

// ErrNoProbe is the sentinel error recorded on the database check
// when Check is called with DatabaseProbe == nil.
var ErrNoProbe = stringErr("no probe configured")

type stringErr string

func (e stringErr) Error() string { return string(e) }

// Check runs every readiness check and returns the resulting Report.
//
// Ready is true only when EVERY critical check (database, data_dir)
// passes. local_first is informational and is always recorded as
// ok: true (a remote database is a valid deployment).
func Check(ctx context.Context, opts Options) (*Report, error) {
	if ctx == nil {
		ctx = context.Background()
	}
	checks := make(map[string]CheckResult, 3)

	checks["database"] = checkDatabase(ctx, opts.DatabaseProbe)
	checks["data_dir"] = checkDataDir(opts.DataDir)

	local := IsLocalFirst(opts.DatabaseURL)
	checks["local_first"] = CheckResult{OK: true, Local: &local}

	ready := checks["database"].OK && checks["data_dir"].OK && checks["local_first"].OK
	return &Report{
		Ready:      ready,
		Version:    opts.Version,
		Checks:     checks,
		Timestamp:  time.Now().UTC().Format(time.RFC3339),
		LocalFirst: local,
	}, nil
}

// checkDatabase pings the database if a probe is supplied. A nil
// probe records the sentinel "no probe configured" error.
func checkDatabase(ctx context.Context, probe Probe) CheckResult {
	if probe == nil {
		return CheckResult{OK: false, Error: ErrNoProbe.Error()}
	}
	// Use a tight timeout so a wedged DB does not stall the
	// readiness probe. 2s is the conventional upper bound for an
	// orchestrator health check.
	cctx, cancel := context.WithTimeout(ctx, 2*time.Second)
	defer cancel()
	if err := probe.Ping(cctx); err != nil {
		return CheckResult{OK: false, Error: err.Error()}
	}
	return CheckResult{OK: true}
}

// checkDataDir auto-creates the directory (mimicking
// os.makedirs(..., exist_ok=True)) and confirms it is writable by
// writing a unique probe file and deleting it.
func checkDataDir(dataDir string) CheckResult {
	if dataDir == "" {
		return CheckResult{OK: false, Error: "dataDir is empty"}
	}
	if err := os.MkdirAll(dataDir, 0o755); err != nil {
		return CheckResult{OK: false, Error: err.Error(), Path: dataDir}
	}

	// 16 hex chars is plenty for a collision-resistant temp
	// probe name within a single readiness call.
	var rnd [8]byte
	if _, err := rand.Read(rnd[:]); err != nil {
		return CheckResult{OK: false, Error: err.Error(), Path: dataDir}
	}
	probe := filepath.Join(dataDir, ".ready_probe_"+hex.EncodeToString(rnd[:]))
	if err := os.WriteFile(probe, []byte("ok"), 0o644); err != nil {
		return CheckResult{OK: false, Error: err.Error(), Path: dataDir}
	}
	if err := os.Remove(probe); err != nil {
		// The probe was written successfully; the directory is
		// still proven writable. A failed remove is a soft
		// failure — record it but still mark ok=true so a
		// non-fatal cleanup race does not flip readiness.
		return CheckResult{
			OK:    true,
			Path:  dataDir,
			Error: "probe remove failed: " + err.Error(),
		}
	}
	return CheckResult{OK: true, Path: dataDir}
}

// IsLocalFirst reports whether databaseURL targets a local store:
// sqlite-prefixed, or contains "localhost" / "127.0.0.1". This is the
// exact heuristic the Python source uses.
func IsLocalFirst(databaseURL string) bool {
	if strings.HasPrefix(databaseURL, "sqlite") {
		return true
	}
	if strings.Contains(databaseURL, "localhost") {
		return true
	}
	if strings.Contains(databaseURL, "127.0.0.1") {
		return true
	}
	return false
}

// String renders the report as an indented JSON string. Convenience
// helper for CLI demos and tests.
func (r *Report) String() string {
	b, err := json.MarshalIndent(r, "", "  ")
	if err != nil {
		return fmt.Sprintf("readiness.Report: marshal failed: %v", err)
	}
	return string(b)
}
