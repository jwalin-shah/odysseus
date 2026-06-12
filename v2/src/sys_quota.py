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


def _parse_window(spec):
    """Parse a window spec like '5m' or '2h' into seconds; return None if spec is None."""
    if spec is None:
        return None
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    return float(spec[:-1]) * units[spec[-1]]


def _ensure_table(conn):
    """Create quota table if it doesn't exist."""
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
    try:
        _ensure_table(conn)
        window_s = _parse_window(args.window)
        window_start = _now() if window_s else None

        # Handle --tokens and --cost as multi-dimensional init
        if args.tokens is not None or args.cost is not None:
            if args.tokens is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO quota (dim, lim, used, window_s, window_start) VALUES (?, ?, 0, ?, ?)",
                    ("tokens", float(args.tokens), window_s, window_start),
                )
            if args.cost is not None:
                conn.execute(
                    "INSERT OR REPLACE INTO quota (dim, lim, used, window_s, window_start) VALUES (?, ?, 0, ?, ?)",
                    ("cost", float(args.cost), window_s, window_start),
                )
        else:
            limit = args.limit
            if limit is None:
                print("ERROR: --limit, --tokens, or --cost is required", file=sys.stderr)
                return 1
            dim = getattr(args, "type", None) or "tokens"
            conn.execute(
                "INSERT OR REPLACE INTO quota (dim, lim, used, window_s, window_start) VALUES (?, ?, 0, ?, ?)",
                (dim, float(limit), window_s, window_start),
            )
    finally:
        conn.close()
    return 0


def cmd_deduct(args):
    """Atomically deduct amount from a quota dimension, exiting 75 if exhausted, 2 if uninitialized."""
    conn = _connect(args.db)
    try:
        conn.execute("BEGIN IMMEDIATE")
        _ensure_table(conn)
        state = _load(conn, args.type)
        if state is None:
            conn.execute("ROLLBACK")
            return 2
        lim, used, _win, _ws = state
        if used + args.amount > lim:
            conn.execute("ROLLBACK")
            print("QUOTA_EXHAUSTED", file=sys.stderr)
            return QUOTA_EXHAUSTED_EXIT
        conn.execute(
            "UPDATE quota SET used=used+? WHERE dim=?",
            (args.amount, args.type),
        )
        conn.execute("COMMIT")
        return 0
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        conn.close()


def cmd_check(args):
    """Check remaining quota for a dimension, exiting 2 if uninitialized."""
    conn = _connect(args.db)
    try:
        _ensure_table(conn)
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
    p.add_argument("--db", default="quota.db", help="Path to SQLite quota database")
    sub = p.add_subparsers(dest="cmd")

    pi = sub.add_parser("init")
    pi.add_argument("--db", default="quota.db")
    pi.add_argument("--limit", type=float, default=None)
    pi.add_argument("--tokens", type=float, default=None)
    pi.add_argument("--cost", type=float, default=None)
    pi.add_argument("--window", default=None)
    pi.add_argument("--type", default="tokens")

    pd = sub.add_parser("deduct")
    pd.add_argument("--db", default="quota.db")
    pd.add_argument("--type", default="tokens")
    pd.add_argument("--amount", type=float, required=True)

    pc = sub.add_parser("check")
    pc.add_argument("--db", default="quota.db")
    pc.add_argument("--type", default="tokens")

    args = p.parse_args(argv)
    if args.cmd == "init":
        return cmd_init(args)
    elif args.cmd == "deduct":
        return cmd_deduct(args)
    elif args.cmd == "check":
        return cmd_check(args)
    else:
        p.print_help()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
