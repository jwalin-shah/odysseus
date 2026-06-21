// Package readiness runs the local-instance readiness checks for the
// Odysseus service. It mirrors the Python `check_readiness` helper from
// src/readiness.py: a single aggregate Report that records database,
// data-directory, and local-first checks.
//
// The package is stdlib-only. The database probe is injected via Config
// so callers can wire their own driver (and so the package itself does
// not depend on a SQL driver).
package readiness

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"time"
)

// Check is the per-check result. Optional fields use omitempty so the
// JSON shape matches the Python implementation, which only includes
// `error` or `path` when populated.
type Check struct {
	Name    string         `json:"-"`
	OK      bool           `json:"ok"`
	Error   string         `json:"error,omitempty"`
	Details map[string]any `json:"-"`
}

// Report is the aggregated readiness report. Timestamp is marshaled as
// RFC3339Nano (ISO 8601 compatible) in UTC to match Python's
// `datetime.utcnow().isoformat()`.
type Report struct {
	Ready     bool      `json:"ready"`
	Version   string    `json:"version"`
	Checks    []Check   `json:"checks"`
	Timestamp time.Time `json:"timestamp"`
}

// Config carries the inputs needed to run the checks. The database
// probe is injected so this package stays free of SQL driver deps.
type Config struct {
	AppVersion  string
	DataDir     string
	DatabaseURL string
	DBProbe     func(ctx context.Context) error
}

// runDBCheck executes the database probe if one is configured.
func runDBCheck(ctx context.Context, cfg Config) Check {
	if cfg.DBProbe == nil {
		return Check{
			Name:  "database",
			OK:    false,
			Error: "no database probe registered",
		}
	}
	if err := cfg.DBProbe(ctx); err != nil {
		return Check{
			Name:  "database",
			OK:    false,
			Error: err.Error(),
		}
	}
	return Check{Name: "database", OK: true}
}

// runDataDirCheck ensures the data directory exists and is writable by
// writing and removing a unique probe file.
func runDataDirCheck(ctx context.Context, cfg Config) Check {
	if err := os.MkdirAll(cfg.DataDir, 0o755); err != nil {
		return Check{
			Name:  "data_dir",
			OK:    false,
			Error: err.Error(),
		}
	}
	// Respect context cancellation for callers that want prompt return.
	if err := ctx.Err(); err != nil {
		return Check{
			Name:  "data_dir",
			OK:    false,
			Error: err.Error(),
		}
	}
	token, err := randomHex(16)
	if err != nil {
		return Check{
			Name:  "data_dir",
			OK:    false,
			Error: err.Error(),
		}
	}
	probe := fmt.Sprintf(".ready_probe_%s", token)
	full := fmt.Sprintf("%s%c%s", cfg.DataDir, os.PathSeparator, probe)
	if err := os.WriteFile(full, []byte("ok"), 0o644); err != nil {
		return Check{
			Name:  "data_dir",
			OK:    false,
			Error: err.Error(),
		}
	}
	if err := os.Remove(full); err != nil {
		return Check{
			Name:  "data_dir",
			OK:    false,
			Error: err.Error(),
		}
	}
	return Check{
		Name:    "data_dir",
		OK:      true,
		Details: map[string]any{"path": cfg.DataDir},
	}
}

// runLocalFirstCheck reports whether the configured database URL points
// at a local instance. This is informational only — it never fails the
// readiness report, matching the Python original.
func runLocalFirstCheck(cfg Config) Check {
	local := isLocal(cfg.DatabaseURL)
	return Check{
		Name:    "local_first",
		OK:      true,
		Details: map[string]any{"local": local},
	}
}

// isLocal reports whether the given URL targets a local database.
// Mirrors Python: starts with "sqlite", or contains "localhost", or
// contains "127.0.0.1".
func isLocal(url string) bool {
	if strings.HasPrefix(url, "sqlite") {
		return true
	}
	if strings.Contains(url, "localhost") {
		return true
	}
	if strings.Contains(url, "127.0.0.1") {
		return true
	}
	return false
}

// randomHex returns n random bytes encoded as lowercase hex. It uses
// crypto/rand so we don't pull in a UUID dependency just for probe
// filenames.
func randomHex(n int) (string, error) {
	buf := make([]byte, n)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return hex.EncodeToString(buf), nil
}

// Run executes the readiness checks in order and returns a Report.
// Ready is true only when every critical check (database, data_dir)
// passes. local_first is informational and always reports ok=true.
func Run(ctx context.Context, cfg Config) Report {
	db := runDBCheck(ctx, cfg)
	dataDir := runDataDirCheck(ctx, cfg)
	localFirst := runLocalFirstCheck(cfg)

	checks := []Check{db, dataDir, localFirst}
	ready := true
	for _, c := range checks {
		if !c.OK {
			ready = false
			break
		}
	}

	return Report{
		Ready:     ready,
		Version:   cfg.AppVersion,
		Checks:    checks,
		Timestamp: time.Now().UTC(),
	}
}

// PingDB is a small convenience for callers that want a stdlib-style
// health probe. It intentionally returns an error for schemes it does
// not know how to drive — drivers should be registered by the caller
// via Config.DBProbe instead of pulling dependencies into this package.
func PingDB(ctx context.Context, url string) error {
	switch {
	case strings.HasPrefix(url, "sqlite"), strings.HasPrefix(url, "file:"):
		return fmt.Errorf("sqlite driver not registered: provide Config.DBProbe")
	case strings.HasPrefix(url, "postgres"), strings.HasPrefix(url, "postgresql"):
		return fmt.Errorf("postgres driver not registered: provide Config.DBProbe")
	default:
		return fmt.Errorf("unsupported database scheme: %q", url)
	}
}

// MarshalJSON renders a Check using only the keys present in the
// Python implementation: `ok` always, `error` only when set, `path`
// only for the data_dir check, and `local` only for local_first.
func (c Check) MarshalJSON() ([]byte, error) {
	m := map[string]any{"ok": c.OK}
	if c.Error != "" {
		m["error"] = c.Error
	}
	if c.Details != nil {
		for k, v := range c.Details {
			m[k] = v
		}
	}
	return json.Marshal(m)
}
