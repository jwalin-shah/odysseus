# core/code_run_store.py
"""Lightweight in-memory + JSONL-backed store for async code-dispatch runs.

This is the "existing infrastructure" reuse point for async code tasks submitted
via POST /api/route with sync=False. Instead of blocking the HTTP request for up
to 300s, we:
  1. Generate a run_id, persist a "submitted" record here.
  2. Fire asyncio.create_task() to run the CLI in the background.
  3. Return the run_id to the caller immediately.
  4. When the background task completes, call finalize_run() to record the
     final status/tokens/latency and update the JSONL log.

Status values mirror TaskRun: "submitted" → "running" → "success" | "error".

The JSONL backing file is append-only (one line per status change) and lives
alongside the orchestration traces so the agent-audit script can read it.
The in-memory dict is the hot path; the file is the durable audit log.
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from core.constants import DATA_DIR

_RUN_DIR = os.path.join(DATA_DIR, "orchestration")
_RUN_FILE = os.path.join(_RUN_DIR, "code_runs.jsonl")

_store: Dict[str, Dict[str, Any]] = {}  # run_id → record
_store_lock = threading.Lock()
_file_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _append_line(record: Dict[str, Any]) -> None:
    """Append one JSON line to the run log. Never raises."""
    try:
        line = json.dumps(record, ensure_ascii=False)
        with _file_lock:
            os.makedirs(_RUN_DIR, exist_ok=True)
            with open(_RUN_FILE, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except OSError:
        pass


def create_run(
    task: str,
    *,
    parent_run_id: Optional[str] = None,
) -> str:
    """Register a new run, return its run_id.

    ``parent_run_id`` links a followup run to the original dispatch run.
    """
    run_id = str(uuid.uuid4())
    record: Dict[str, Any] = {
        "run_id": run_id,
        "task_hash": _task_hash(task),
        "status": "submitted",
        "submitted_at": _now_iso(),
        "submitted_unix": round(time.time(), 3),
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
        "tokens": 0,
        "latency_ms": 0.0,
        # session / provider fields — populated by finalize_run
        "session_id": None,
        "adapter_name": None,
        "parent_run_id": parent_run_id,
    }
    with _store_lock:
        _store[run_id] = record
    _append_line({**record, "_event": "submitted"})
    return run_id


def mark_running(run_id: str) -> None:
    """Flip status to 'running' when the background task starts executing."""
    with _store_lock:
        rec = _store.get(run_id)
        if rec:
            rec["status"] = "running"
            rec["started_at"] = _now_iso()
    _append_line({"run_id": run_id, "_event": "running", "ts": _now_iso()})


def finalize_run(
    run_id: str,
    *,
    success: bool,
    result: Optional[str] = None,
    error: Optional[str] = None,
    tokens: int = 0,
    latency_ms: float = 0.0,
    session_id: Optional[str] = None,
    adapter_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Record the completion of an async code run. Returns the final record.

    ``session_id`` is the claude session_id extracted from JSON output (if any).
    ``adapter_name`` is the logical adapter name (e.g. "claude-ca", "codex").
    """
    finished = _now_iso()
    status = "success" if success else "error"
    with _store_lock:
        rec = _store.get(run_id, {})
        rec.update(
            status=status,
            finished_at=finished,
            result=(result or "")[:4000],
            error=(str(error)[:500] if error else None),
            tokens=int(tokens or 0),
            latency_ms=round(float(latency_ms), 1),
        )
        if session_id is not None:
            rec["session_id"] = session_id
        if adapter_name is not None:
            rec["adapter_name"] = adapter_name
        updated = dict(rec)
    _append_line({**updated, "_event": "finalized"})
    return updated


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Return the current record for run_id, or None if not found."""
    with _store_lock:
        rec = _store.get(run_id)
        return dict(rec) if rec else None


def _task_hash(task: str) -> str:
    import hashlib
    return hashlib.sha256(task.encode("utf-8", errors="replace")).hexdigest()[:16]
