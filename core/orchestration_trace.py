# core/orchestration_trace.py
"""Orchestration observability — trace receipts, aggregates, health probes.

Every routed task gets one JSONL receipt. The trace is the evidence layer for
the Router → Supervisor → Pipeline stack: it answers "what did the router do,
what did it cost, and is the orchestration actually helping".

Design constraints (see platform/ORCHESTRATION.md):
* Append-only JSONL, thread-safe — FastAPI is async and multi-worker-capable,
  so writes hold a lock and emit exactly one line per receipt.
* Aggregates have fixed cardinality: (classification, model_used, time bucket)
  only. ``task_hash`` exists for forensics and is never an aggregation key.
* Latency percentiles are computed over ALL completed dispatches, including
  failures and timeouts (which cap at the router's 300 s subprocess limit).
  Success rate is reported separately so the two are never conflated.
* Health is probed, not parsed: quota freshness checks the file's own
  timestamp, CLI liveness actually executes the binary.
"""

import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.constants import DATA_DIR

TRACE_DIR = os.path.join(DATA_DIR, "orchestration")
TRACE_FILE = os.path.join(TRACE_DIR, "traces.jsonl")

QUOTA_LIVE_PATH = (
    "/Users/jwalinshah/projects/platform/systems/quota-core/data/quota-live.json"
)
QUOTA_STALE_SECONDS = 600
# Accounts to probe: (label, CLAUDE_CONFIG_DIR). `ca`/`cb` are zsh functions,
# not binaries — the real mechanism is the `claude` binary plus a config dir,
# so that is what gets probed. (Probing the literal name `cp` finds /bin/cp.)
CLI_PROBE_ACCOUNTS = (
    ("ca", "~/.claude-a"),
    ("cb", "~/.claude-b"),
)
CLI_PROBE_TTL = 60  # seconds; probing runs subprocesses, so cache results
PROC_PRESSURE_THRESHOLD = 0.85  # fraction of ulimit -u that counts as unhealthy

_write_lock = threading.Lock()
_cli_probe_cache: Dict[str, Any] = {"ts": 0.0, "result": None}


def task_hash(task: str) -> str:
    """Stable 16-hex-char digest of the task text. Forensics only."""
    return hashlib.sha256(task.encode("utf-8", errors="replace")).hexdigest()[:16]


def record_trace(
    *,
    task: str = "",
    classification: str = "unknown",
    model_used: str = "unknown",
    tokens: int = 0,
    latency_ms: float = 0.0,
    success: bool = True,
    error: Optional[str] = None,
    source: str = "router",
) -> Dict[str, Any]:
    """Append one trace receipt. Never raises — observability must not break
    the request it observes. Returns the receipt that was written (or that
    failed to write, with ``_write_error`` set)."""
    now = time.time()
    receipt: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "unix": round(now, 3),
        "task_hash": task_hash(task) if task else None,
        "classification": classification,
        "model_used": model_used,
        "tokens": int(tokens or 0),
        "latency_ms": round(float(latency_ms), 1),
        "success": bool(success),
        "error": (str(error)[:500] if error else None),
        "source": source,
    }
    line = json.dumps(receipt, ensure_ascii=False)
    try:
        with _write_lock:
            os.makedirs(TRACE_DIR, exist_ok=True)
            with open(TRACE_FILE, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except OSError as exc:
        receipt["_write_error"] = str(exc)
    return receipt


def read_traces(
    limit: int = 100,
    offset: int = 0,
    since_unix: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Newest-first page of receipts. Malformed lines are skipped, not fatal."""
    rows: List[Dict[str, Any]] = []
    try:
        with open(TRACE_FILE, "r", encoding="utf-8") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    row = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if since_unix is not None and row.get("unix", 0) < since_unix:
                    continue
                rows.append(row)
    except FileNotFoundError:
        return []
    rows.reverse()
    return rows[offset : offset + max(0, limit)]


def _percentile(sorted_vals: List[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    idx = min(len(sorted_vals) - 1, max(0, round(pct / 100 * (len(sorted_vals) - 1))))
    return sorted_vals[idx]


def _window_stats(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    latencies = sorted(float(r.get("latency_ms", 0)) for r in rows)
    successes = sum(1 for r in rows if r.get("success"))
    by_bucket: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        # Fixed cardinality: classification × model only. Never task_hash.
        key = f"{r.get('classification', 'unknown')}|{r.get('model_used', 'unknown')}"
        b = by_bucket.setdefault(
            key,
            {
                "classification": r.get("classification", "unknown"),
                "model_used": r.get("model_used", "unknown"),
                "count": 0,
                "tokens": 0,
                "failures": 0,
            },
        )
        b["count"] += 1
        b["tokens"] += int(r.get("tokens", 0) or 0)
        if not r.get("success"):
            b["failures"] += 1
    return {
        "count": len(rows),
        "success_rate": round(successes / len(rows), 4) if rows else None,
        # Percentiles over ALL completed dispatches incl. failures/timeouts.
        "latency_ms_p50": _percentile(latencies, 50),
        "latency_ms_p95": _percentile(latencies, 95),
        "by_classification_model": sorted(
            by_bucket.values(), key=lambda b: -b["count"]
        ),
    }


def compute_stats() -> Dict[str, Any]:
    """Rolling 24 h / 7 d aggregates with bounded cardinality."""
    now = time.time()
    week = read_traces(limit=1_000_000, since_unix=now - 7 * 86400)
    day = [r for r in week if r.get("unix", 0) >= now - 86400]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "latency_definition": (
            "p50/p95 over all completed dispatches in the window, including "
            "failures and 300s-capped timeouts; success_rate reported separately"
        ),
        "last_24h": _window_stats(day),
        "last_7d": _window_stats(week),
    }


def _probe_quota_freshness() -> Dict[str, Any]:
    """Probe the quota file's own timestamps — existence is not freshness."""
    try:
        mtime = os.path.getmtime(QUOTA_LIVE_PATH)
    except OSError:
        return {"ok": False, "reason": "quota-live.json missing or unreadable"}
    age = time.time() - mtime
    inner_age = None
    try:
        with open(QUOTA_LIVE_PATH, "r", encoding="utf-8") as fh:
            unix_ts = json.load(fh).get("unix")
        if unix_ts:
            inner_age = round(time.time() - float(unix_ts), 1)
    except (OSError, json.JSONDecodeError, ValueError):
        pass
    stale = age > QUOTA_STALE_SECONDS or (
        inner_age is not None and inner_age > QUOTA_STALE_SECONDS
    )
    return {
        "ok": not stale,
        "file_age_s": round(age, 1),
        "data_age_s": inner_age,
        "stale_threshold_s": QUOTA_STALE_SECONDS,
    }


def _probe_cli_liveness() -> Dict[str, Any]:
    """Run `claude --version` once, then check each account's config dir.

    ``which`` can't distinguish broken PATH, broken binary, or missing config —
    execution can. Results are cached for CLI_PROBE_TTL seconds."""
    now = time.time()
    if _cli_probe_cache["result"] and now - _cli_probe_cache["ts"] < CLI_PROBE_TTL:
        return _cli_probe_cache["result"]
    statuses: Dict[str, Any] = {}
    claude_bin = shutil.which("claude")
    if not claude_bin:
        binary_ok, binary_detail = False, "claude binary not on PATH"
    else:
        try:
            proc = subprocess.run(
                [claude_bin, "--version"], capture_output=True, text=True, timeout=5
            )
            binary_ok = proc.returncode == 0
            binary_detail = (proc.stdout or proc.stderr).strip()[:120]
        except subprocess.TimeoutExpired:
            binary_ok, binary_detail = False, "timed out (5s)"
        except OSError as exc:
            binary_ok, binary_detail = False, str(exc)[:120]
    for account, config_dir in CLI_PROBE_ACCOUNTS:
        cfg = os.path.expanduser(config_dir)
        cfg_ok = os.path.isdir(cfg)
        statuses[account] = {
            "ok": binary_ok and cfg_ok,
            "detail": binary_detail if not cfg_ok else f"config: {cfg}",
        }
        if not cfg_ok:
            statuses[account]["detail"] = f"config dir missing: {cfg}"
    result = {
        "ok": binary_ok and any(s["ok"] for s in statuses.values()),
        "claude_binary": {"ok": binary_ok, "detail": binary_detail},
        "accounts": statuses,
    }
    _cli_probe_cache.update(ts=now, result=result)
    return result


def _probe_process_pressure() -> Dict[str, Any]:
    """Detect per-user process exhaustion — the condition where every
    fork-dependent component (hooks, key resolution, CLI dispatch) starts
    failing with EAGAIN wearing unrelated error messages."""
    try:
        # absolute paths: the server's launchd PATH may lack /usr/sbin
        count = len(
            subprocess.run(
                ["/bin/ps", "-u", str(os.getuid()), "-o", "pid="],
                capture_output=True, text=True, timeout=5,
            ).stdout.splitlines()
        )
        limit = int(
            subprocess.run(
                ["/usr/sbin/sysctl", "-n", "kern.maxprocperuid"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {"ok": True, "detail": f"probe unavailable: {exc}"}
    ratio = count / limit if limit else 0.0
    result: Dict[str, Any] = {
        "ok": ratio < PROC_PRESSURE_THRESHOLD,
        "processes": count,
        "limit": limit,
        "ratio": round(ratio, 3),
    }
    if not result["ok"]:
        # Name the culprit so the next EAGAIN isn't a mystery
        top = subprocess.run(
            ["/bin/ps", "-u", str(os.getuid()), "-o", "comm="],
            capture_output=True, text=True, timeout=5,
        ).stdout.splitlines()
        counts: Dict[str, int] = {}
        for c in top:
            base = os.path.basename(c.strip())
            counts[base] = counts.get(base, 0) + 1
        result["top_commands"] = sorted(
            counts.items(), key=lambda kv: -kv[1]
        )[:3]
    return result


def _failure_streak(rows_newest_first: List[Dict[str, Any]]) -> int:
    """Consecutive failures at the head of the trace — not last-N totals."""
    streak = 0
    for row in rows_newest_first:
        if row.get("success"):
            break
        streak += 1
    return streak


def compute_health() -> Dict[str, Any]:
    quota = _probe_quota_freshness()
    cli = _probe_cli_liveness()
    pressure = _probe_process_pressure()
    streak = _failure_streak(read_traces(limit=50))
    healthy = quota["ok"] and cli["ok"] and pressure["ok"] and streak < 3
    return {
        "healthy": healthy,
        "quota_core": quota,
        "cli": cli,
        "process_pressure": pressure,
        "consecutive_failures": streak,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
