"""Tests for the dispatch wait / status / log-tail surface.

These tools close the loop so a caller can dispatch + iterate without
manually polling .credit-lab/ody/ from a separate shell.

- dispatch_mission(wait=true, wait_timeout=N): block until the worker
  subprocess exits, then return the feedback record.
- do_dispatch_status(dispatch_id): look up the current state.
- do_dispatch_log_tail(dispatch_id, since_bytes=0): tail the worker log.
"""
import asyncio
import json
import os
import pathlib
import subprocess
import sys
import time

import pytest

from src import tool_implementations


# --------------------------------------------------------------------------- #
# helpers                                                                     #
# --------------------------------------------------------------------------- #

class _ImmediateProcess:
    """A Popen stand-in that exits as soon as wait() is called."""
    pid = 910001
    returncode = 0


def _patch_popen_to_exit_immediately(monkeypatch):
    """Make subprocess.Popen return a process that exits right away."""
    def popen(cmd, **kwargs):
        return _ImmediateProcess()
    monkeypatch.setattr(subprocess, "Popen", popen)


def _write_feedback(log_dir, dispatch_id, payload):
    """Drop a feedback file that looks like a real worker output.

    Stamps the record with ``dispatch_id`` so ``_find_feedback`` can match
    it back to the dispatch. Real workers do this via write_feedback() in
    odysseus.py when ODY_DISPATCH_ID is in the env.
    """
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{int(time.time() * 1000)}.jsonl"
    record = dict(payload)
    record["dispatch_id"] = dispatch_id
    path.write_text(json.dumps(record) + "\n")
    # Bump mtime to "now" so status sorts it as the most recent.
    os.utime(path, (time.time(), time.time()))
    return path


# --------------------------------------------------------------------------- #
# (1) wait=true: returns the feedback record when the worker exits            #
# --------------------------------------------------------------------------- #

def test_dispatch_mission_wait_blocks_until_worker_exits(tmp_path, monkeypatch):
    """With wait=true, the caller gets the worker's feedback without polling."""
    _patch_popen_to_exit_immediately(monkeypatch)
    tool_implementations.MISSION_LOG_DIR = tmp_path

    payload = json.dumps({
        "mission": "wait-true test",
        "repo": "/tmp/repo",
        "test": "pytest -q",
        "wait": True,
        "wait_timeout": 5,
    })

    # Pre-seed a feedback file that the worker would have written,
    # stamped with the dispatch_id the wait loop will look for.
    dispatched = asyncio.run(tool_implementations.do_dispatch_mission(payload))
    _write_feedback(tmp_path, dispatched["dispatch_id"], {
        "agent_used": "claude", "result": "ok", "test_passed": True,
        "branch": "ody-claude-test", "duration": 1.2,
    })
    # Re-run with wait=true; the worker is a no-op (mock Popen), so we
    # need a fresh dispatch surface. Simplest: call the wait helper
    # directly to prove the wait loop finds the feedback.
    from src.tool_implementations import _wait_for_feedback
    class _MockProc:
        pid = 4242
    feedback = _wait_for_feedback(tmp_path, dispatched["dispatch_id"],
                                  _MockProc(), 5)
    assert feedback is not None
    assert feedback["test_passed"] is True
    assert feedback["branch"] == "ody-claude-test"


def test_dispatch_mission_wait_times_out_when_no_feedback(tmp_path, monkeypatch):
    """If the worker never writes feedback, wait=true returns wait_timeout."""
    _patch_popen_to_exit_immediately(monkeypatch)
    tool_implementations.MISSION_LOG_DIR = tmp_path

    payload = json.dumps({
        "mission": "wait-timeout test",
        "repo": "/tmp/repo",
        "test": "pytest -q",
        "wait": True,
        "wait_timeout": 1,  # short; the patched Popen exits immediately,
                             # but no feedback file is written, so we
                             # exhaust the budget polling the dir.
    })

    # Call the wait helper directly with a tight budget and no feedback
    # file in the dir. It must return None within the budget.
    from src.tool_implementations import _wait_for_feedback
    class _MockProc:
        pid = 4242
    t0 = time.time()
    feedback = _wait_for_feedback(tmp_path, "d_no_feedback", _MockProc(), 1)
    elapsed = time.time() - t0

    assert feedback is None, (
        "no feedback file was written, so the wait loop must return None"
    )
    # The wait should have respected the budget; we allow some slack for
    # the process to exit + the initial scan.
    assert elapsed < 5, f"wait should respect the 1s budget; took {elapsed:.1f}s"

    # Also verify the do_dispatch_mission surface: a fresh dispatch with
    # wait=true and no feedback should return finished=False.
    rec = asyncio.run(tool_implementations.do_dispatch_mission(payload))
    assert rec["exit_code"] == 0
    assert rec.get("wait") is True
    assert rec.get("finished") is False, (
        "no feedback file was written, so wait=true must report not-finished"
    )


def test_dispatch_mission_default_is_fire_and_forget(tmp_path, monkeypatch):
    """With no wait arg, dispatch returns immediately, no feedback polling."""
    _patch_popen_to_exit_immediately(monkeypatch)
    tool_implementations.MISSION_LOG_DIR = tmp_path

    payload = json.dumps({
        "mission": "fire-and-forget test",
        "repo": "/tmp/repo",
        "test": "pytest -q",
    })
    rec = asyncio.run(tool_implementations.do_dispatch_mission(payload))
    assert rec["exit_code"] == 0
    assert "feedback" not in rec, (
        "default mode is fire-and-forget; feedback must not be returned"
    )
    assert rec.get("wait") is False or rec.get("wait") is None


# --------------------------------------------------------------------------- #
# (2) do_dispatch_status: report the current state of a dispatch               #
# --------------------------------------------------------------------------- #

def test_dispatch_status_reports_unfinished(tmp_path, monkeypatch):
    """Status of a fresh dispatch (no feedback yet) is finished=false."""
    _patch_popen_to_exit_immediately(monkeypatch)
    tool_implementations.MISSION_LOG_DIR = tmp_path

    payload = json.dumps({
        "mission": "status-unfinished test",
        "repo": "/tmp/repo",
        "test": "pytest -q",
    })
    dispatched = asyncio.run(tool_implementations.do_dispatch_mission(payload))
    assert dispatched["exit_code"] == 0

    status = asyncio.run(tool_implementations.do_dispatch_status(
        json.dumps({"dispatch_id": dispatched["dispatch_id"]})
    ))
    assert status["exit_code"] == 0
    assert status["dispatch_id"] == dispatched["dispatch_id"]
    assert status["finished"] is False
    assert status["pid_alive"] is False  # the mock process exits immediately


def test_dispatch_status_reports_finished(tmp_path, monkeypatch):
    """Status picks up the most recent feedback file for the dispatch."""
    _patch_popen_to_exit_immediately(monkeypatch)
    tool_implementations.MISSION_LOG_DIR = tmp_path

    payload = json.dumps({
        "mission": "status-finished test",
        "repo": "/tmp/repo",
        "test": "pytest -q",
    })
    dispatched = asyncio.run(tool_implementations.do_dispatch_mission(payload))

    # Stamp the feedback with the dispatch's id (not a hardcoded one) so
    # _find_feedback can match it.
    _write_feedback(tmp_path, dispatched["dispatch_id"], {
        "agent_used": "claude", "result": "ok", "test_passed": True,
        "branch": "ody-claude-status-finished", "duration": 7.7,
    })

    status = asyncio.run(tool_implementations.do_dispatch_status(
        json.dumps({"dispatch_id": dispatched["dispatch_id"]})
    ))
    assert status["exit_code"] == 0
    assert status["finished"] is True
    assert status["feedback"]["test_passed"] is True
    assert status["feedback"]["branch"] == "ody-claude-status-finished"


def test_dispatch_status_unknown_id(tmp_path, monkeypatch):
    """An unknown dispatch_id returns a clean error, not a crash."""
    status = asyncio.run(tool_implementations.do_dispatch_status(
        json.dumps({"dispatch_id": "d_does_not_exist_1234"})
    ))
    assert status["exit_code"] == 1
    assert "error" in status


# --------------------------------------------------------------------------- #
# (3) do_dispatch_log_tail: stream the worker's log                           #
# --------------------------------------------------------------------------- #

def test_dispatch_log_tail_returns_full_log(tmp_path, monkeypatch):
    _patch_popen_to_exit_immediately(monkeypatch)
    tool_implementations.MISSION_LOG_DIR = tmp_path

    payload = json.dumps({
        "mission": "log-tail test",
        "repo": "/tmp/repo",
        "test": "pytest -q",
    })
    dispatched = asyncio.run(tool_implementations.do_dispatch_mission(payload))

    log_path = pathlib.Path(dispatched["log"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("line 1\nline 2\nline 3\n")

    tail = asyncio.run(tool_implementations.do_dispatch_log_tail(
        json.dumps({"dispatch_id": dispatched["dispatch_id"]})
    ))
    assert tail["exit_code"] == 0
    assert "line 1" in tail["content"]
    assert "line 3" in tail["content"]
    assert tail["total_bytes"] == log_path.stat().st_size


def test_dispatch_log_tail_since_bytes(tmp_path, monkeypatch):
    """since_bytes returns only the content after the given offset."""
    _patch_popen_to_exit_immediately(monkeypatch)
    tool_implementations.MISSION_LOG_DIR = tmp_path

    payload = json.dumps({
        "mission": "log-tail-since test",
        "repo": "/tmp/repo",
        "test": "pytest -q",
    })
    dispatched = asyncio.run(tool_implementations.do_dispatch_mission(payload))
    log_path = pathlib.Path(dispatched["log"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("first\nsecond\nthird\n")

    full = asyncio.run(tool_implementations.do_dispatch_log_tail(
        json.dumps({"dispatch_id": dispatched["dispatch_id"]})
    ))
    offset = full["total_bytes"] - len("third\n")

    delta = asyncio.run(tool_implementations.do_dispatch_log_tail(
        json.dumps({"dispatch_id": dispatched["dispatch_id"],
                    "since_bytes": offset})
    ))
    assert delta["exit_code"] == 0
    assert delta["content"] == "third\n"
    assert delta["start_byte"] == offset
