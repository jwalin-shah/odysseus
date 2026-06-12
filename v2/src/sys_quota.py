"""sys-quota: atomic multi-dimensional quota CLI (V2 spec: v2/tests/test_quota.py).

SQLite WAL + BEGIN IMMEDIATE serializes concurrent deductions so parallel
subagents can never double-spend. Exhaustion exits QUOTA_EXHAUSTED_EXIT (75,
EX_TEMPFAIL) — 429 is not representable in an 8-bit POSIX exit status.
"""
import argparse
import os
import sqlite3
import sys
import time

QUOTA_EXHAUSTED_EXIT = 75


def _now():
    """Return current epoch seconds, optionally shifted for tests."""
    return time.time() + float(os.environ.get("ODY_MOCK_TIME_OFFSET_HOURS", 0)) * 3600
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    ...
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
def _connect(db):
    """Open a SQLite connection with WAL mode and 30s busy timeout."""
    conn = sqlite3.connect(db, timeout=30, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn


def _parse_window(spec):
    """Parse a window spec like '5m' or '2h' into seconds; return None if spec is None."""
    if spec is None:
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return float(spec[:-1]) * units[spec[-1]]


def _load(conn, dim):
    """Load a quota row. Applies a window reset if the window has elapsed."""
    row = conn.execute(
        "SELECT lim, used, window_s, window_start FROM quota WHERE dim=?", (dim,)
    ).fetchone()
    if row is None:
        return None
    lim, used, window_s, window_start = row
    if window_s and window_start is not None and (_now() - window_start) >= window_s:
        conn.execute(
            "UPDATE quota SET used=0, window_start=? WHERE dim=?",
            (_now(), dim),
        )
        used = 0
    return (lim, used, window_s, window_start)


def cmd_init(args):
    """Initialize the quota database with the given dimensions, limits, and optional time window."""
    conn = _connect(args.db)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS quota (
            dim TEXT PRIMARY KEY,
            lim REAL NOT NULL,
            used REAL NOT NULL DEFAULT 0,
            window_s REAL,
            window_start REAL
        )
        """
    )
    limit = args.limit if args.limit is not None else (args.tokens if args.tokens is not None else args.cost)
    if limit is None:
        print("ERROR: --limit, --tokens, or --cost is required", file=sys.stderr)
        return 1
    dim = getattr(args, "type", None) or "tokens"
    window_s = _parse_window(args.window)
    window_start = _now() if window_s else None
    conn.execute(
        "INSERT OR REPLACE INTO quota (dim, lim, used, window_s, window_start) VALUES (?, ?, 0, ?, ?)",
        (dim, limit, window_s, window_start),
    )
    conn.commit()
    conn.close()
    return 0


def cmd_deduct(args):
    """Atomically deduct amount from a quota dimension, exiting 75 if exhausted, 2 if uninitialized."""
    conn = _connect(args.db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        state = _load(conn, args.type)
        if state is None:
            conn.rollback()
            return 2
        lim, used, _win, _ws = state
        if used + args.amount > lim:
            conn.rollback()
            return QUOTA_EXHAUSTED_EXIT
def cmd_check(args):
    """Check remaining quota for a dimension, exiting 2 if uninitialized."""
    conn = _connect(args.db)
    try:
        state = _load(conn, args.type)
        if state is None:
            return 2
        lim, used, _win, _ws = state
        print(f"REMAINING: {lim - used:g}")
        return 0
    finally:
        conn.close()
def main(argv=None):
    """Entry point: parse argv and dispatch to init/deduct/check subcommands."""
    p = argparse.ArgumentParser(prog="sys-quota")