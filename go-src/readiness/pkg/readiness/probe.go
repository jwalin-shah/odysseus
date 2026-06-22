// Package readiness is the Go port of src/readiness.py.
//
// The Python source runs three checks for a self-hosted Odysseus instance:
//
//  1. database    — open the SQLAlchemy engine and execute "SELECT 1".
//  2. data_dir    — os.makedirs(DATA_DIR, exist_ok=True), write a probe
//     file, remove it.
//  3. local_first — informational; storage stays on this host iff
//     DATABASE_URL starts with "sqlite", contains "localhost", or
//     contains "127.0.0.1".
//
// ready is true only when EVERY critical check (database, data_dir) passes.
// local_first is informational and never fails readiness — a remote database
// is a valid deployment.
//
// The Go port does NOT import a SQL driver. Instead, the database check is
// plugged in via a small Probe interface so the host process can supply its
// own pool health check (or nil, to record a sentinel failure).
package readiness

import "context"

// Probe is the minimal interface the database check needs from the
// host's connection pool. Stdlib's *sql.DB.PingContext satisfies it
// out of the box:
//
//	probe := readiness.ProbeFunc(db.PingContext)
type Probe interface {
	Ping(ctx context.Context) error
}

// ProbeFunc adapts a plain function into a Probe. A nil ProbeFunc
// pings as nil (no error), so the report records the database check
// as OK — the calling Check call controls nil-handling separately
// through the Options.DatabaseProbe field.
type ProbeFunc func(ctx context.Context) error

// Ping implements Probe.
func (f ProbeFunc) Ping(ctx context.Context) error {
	if f == nil {
		return nil
	}
	return f(ctx)
}
