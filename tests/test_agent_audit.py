"""Tests for scripts/agent-audit.

Three test groups:
1. collect_with_fixture_traces  — write temp JSONL, assert aggregates
2. collect_with_nothing_present — no crash, valid JSON with zeros/nulls
3. diff_fixture_snapshots       — assert specific markdown lines
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Import the script as a module (it has no .py extension)
# ---------------------------------------------------------------------------

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "agent-audit"

spec = importlib.util.spec_from_file_location(
    "agent_audit",
    str(_SCRIPT),
    submodule_search_locations=[],
)
if spec is None or spec.loader is None:
    # Fallback: read and exec the source manually
    import types as _types

    _mod = _types.ModuleType("agent_audit")
    _mod.__file__ = str(_SCRIPT)
    _mod.__spec__ = None  # type: ignore[assignment]
    with open(_SCRIPT, "r", encoding="utf-8") as _fh:
        _src = _fh.read()
    exec(compile(_src, str(_SCRIPT), "exec"), _mod.__dict__)
else:
    _mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(_mod)

# Expose for convenience
collect_traces = _mod.collect_traces
collect_quota = _mod.collect_quota
cmd_collect = _mod.cmd_collect
cmd_diff = _mod.cmd_diff
_window_stats = _mod._window_stats
_load_traces = _mod._load_traces


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_receipt(
    unix: float,
    classification: str = "code",
    model_used: str = "claude-sonnet-4",
    tokens: int = 100,
    latency_ms: float = 250.0,
    success: bool = True,
    error: str | None = None,
) -> Dict[str, Any]:
    return {
        "ts": "2026-06-11T00:00:00.000+00:00",
        "unix": unix,
        "task_hash": "abc123",
        "classification": classification,
        "model_used": model_used,
        "tokens": tokens,
        "latency_ms": latency_ms,
        "success": success,
        "error": error,
        "source": "router",
    }


def _write_trace_file(tmp_dir: Path, receipts: list[Dict[str, Any]]) -> Path:
    trace_dir = tmp_dir / "orchestration"
    trace_dir.mkdir(parents=True, exist_ok=True)
    trace_file = trace_dir / "traces.jsonl"
    with trace_file.open("w") as fh:
        for r in receipts:
            fh.write(json.dumps(r) + "\n")
    return trace_file


# ---------------------------------------------------------------------------
# 1. collect_with_fixture_traces
# ---------------------------------------------------------------------------


class TestCollectWithFixtureTraces:
    """Write fixture JSONL and verify aggregates are correct."""

    def _run_collect(self, receipts: list[Dict[str, Any]]) -> Dict[str, Any]:
        """Patch TRACE_FILE to a temp file, run collect_traces, return result."""
        now = time.time()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace_file = _write_trace_file(tmp_path, receipts)
            with mock.patch.object(_mod, "TRACE_FILE", trace_file):
                return _mod.collect_traces()

    def test_dispatch_count(self):
        now = time.time()
        receipts = [_make_receipt(now - 3600) for _ in range(5)]
        result = self._run_collect(receipts)
        assert result["last_24h"]["count"] == 5
        assert result["last_7d"]["count"] == 5

    def test_success_rate(self):
        now = time.time()
        receipts = [
            _make_receipt(now - 3600, success=True),
            _make_receipt(now - 3600, success=True),
            _make_receipt(now - 3600, success=False),
            _make_receipt(now - 3600, success=False),
        ]
        result = self._run_collect(receipts)
        assert result["last_24h"]["success_rate"] == 0.5
        assert result["last_24h"]["failure_count"] == 2
        assert result["last_24h"]["success_count"] == 2

    def test_window_separation(self):
        """Items older than 24h appear in last_7d but not last_24h."""
        now = time.time()
        receipts = [
            _make_receipt(now - 3600),       # 1h ago — in both windows
            _make_receipt(now - 2 * 86400),  # 2d ago — only in 7d window
        ]
        result = self._run_collect(receipts)
        assert result["last_24h"]["count"] == 1
        assert result["last_7d"]["count"] == 2

    def test_latency_percentiles(self):
        now = time.time()
        receipts = [
            _make_receipt(now - 100, latency_ms=float(ms))
            for ms in [100, 200, 300, 400, 500]
        ]
        result = self._run_collect(receipts)
        p50 = result["last_24h"]["latency_ms_p50"]
        p95 = result["last_24h"]["latency_ms_p95"]
        assert p50 == 300.0
        assert p95 == 500.0

    def test_token_totals(self):
        now = time.time()
        receipts = [_make_receipt(now - 100, tokens=250) for _ in range(4)]
        result = self._run_collect(receipts)
        assert result["last_24h"]["total_tokens"] == 1000

    def test_by_classification_model(self):
        now = time.time()
        receipts = [
            _make_receipt(now - 100, classification="code", model_used="m1"),
            _make_receipt(now - 100, classification="code", model_used="m1"),
            _make_receipt(now - 100, classification="chat", model_used="m2"),
        ]
        result = self._run_collect(receipts)
        buckets = {
            "{}|{}".format(b["classification"], b["model_used"]): b
            for b in result["last_24h"]["by_classification_model"]
        }
        assert buckets["code|m1"]["count"] == 2
        assert buckets["chat|m2"]["count"] == 1

    def test_failures_by_classification(self):
        now = time.time()
        receipts = [
            _make_receipt(now - 100, classification="code", success=False),
            _make_receipt(now - 100, classification="code", success=True),
            _make_receipt(now - 100, classification="chat", success=False),
        ]
        result = self._run_collect(receipts)
        fbc = result["last_24h"]["failures_by_classification"]
        assert fbc["code"] == 1
        assert fbc["chat"] == 1

    def test_trace_file_metadata(self):
        now = time.time()
        receipts = [_make_receipt(now - 100)]
        result = self._run_collect(receipts)
        assert result["trace_file_exists"] is True
        assert result["trace_total_lines"] == 1

    def test_malformed_lines_skipped(self):
        """Malformed JSONL lines must not cause errors."""
        now = time.time()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            trace_dir = tmp_path / "orchestration"
            trace_dir.mkdir()
            trace_file = trace_dir / "traces.jsonl"
            with trace_file.open("w") as fh:
                fh.write(json.dumps(_make_receipt(now - 100)) + "\n")
                fh.write("NOT JSON AT ALL\n")
                fh.write(json.dumps(_make_receipt(now - 200)) + "\n")
            with mock.patch.object(_mod, "TRACE_FILE", trace_file):
                result = _mod.collect_traces()
        assert result["last_24h"]["count"] == 2


# ---------------------------------------------------------------------------
# 2. collect_with_nothing_present
# ---------------------------------------------------------------------------


class TestCollectWithNothingPresent:
    """On a fresh machine with no traces / quota / server, collect must return
    valid JSON with zeros/nulls and never raise."""

    def _full_collect(self) -> Dict[str, Any]:
        """Run the full collect pipeline patched to empty/unreachable state."""
        with tempfile.TemporaryDirectory() as tmp:
            empty_trace = Path(tmp) / "orchestration" / "traces.jsonl"
            empty_quota = Path(tmp) / "quota-live.json"
            with (
                mock.patch.object(_mod, "TRACE_FILE", empty_trace),
                mock.patch.object(_mod, "QUOTA_LIVE_PATH", empty_quota),
                mock.patch.object(
                    _mod, "ORCHESTRATION_HEALTH_URL", "http://localhost:19999"
                ),
            ):
                import io
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    _mod.cmd_collect(None)
                return json.loads(buf.getvalue())

    def test_no_crash(self):
        snap = self._full_collect()
        assert isinstance(snap, dict)

    def test_schema_version_present(self):
        snap = self._full_collect()
        assert snap["schema_version"] == "1"

    def test_snapshot_ts_present(self):
        snap = self._full_collect()
        assert "snapshot_ts" in snap
        assert snap["snapshot_ts"]  # non-empty string

    def test_traces_section_present(self):
        snap = self._full_collect()
        assert "traces" in snap
        assert snap["traces"]["last_24h"]["count"] == 0
        assert snap["traces"]["last_7d"]["count"] == 0

    def test_traces_success_rate_none_when_no_data(self):
        snap = self._full_collect()
        assert snap["traces"]["last_24h"]["success_rate"] is None

    def test_quota_section_graceful(self):
        snap = self._full_collect()
        q = snap["quota"]
        assert q["exists"] is False
        assert q["is_stale"] is True
        assert q["data"] is None

    def test_health_section_graceful(self):
        snap = self._full_collect()
        h = snap["health"]
        assert h["reachable"] is False
        assert "error" in h

    def test_git_section_present(self):
        snap = self._full_collect()
        assert "git" in snap
        assert "odysseus" in snap["git"]
        assert "platform" in snap["git"]

    def test_git_odysseus_has_branch(self):
        snap = self._full_collect()
        # The repo exists, so branch should be set
        g = snap["git"]["odysseus"]
        assert g["exists"] is True
        assert g["branch"] is not None

    def test_sort_keys_deterministic(self):
        """Two calls with same logical inputs produce identical JSON structure
        (ignoring volatile fields: temp paths, timestamps, dirty_file_count)."""
        import io

        def _snap():
            with tempfile.TemporaryDirectory() as tmp:
                empty_trace = Path(tmp) / "orchestration" / "traces.jsonl"
                empty_quota = Path(tmp) / "quota-live.json"
                with (
                    mock.patch.object(_mod, "TRACE_FILE", empty_trace),
                    mock.patch.object(_mod, "QUOTA_LIVE_PATH", empty_quota),
                    mock.patch.object(
                        _mod, "ORCHESTRATION_HEALTH_URL", "http://localhost:19999"
                    ),
                    mock.patch.object(
                        _mod, "_now_utc", return_value="2026-06-11T00:00:00.000+00:00"
                    ),
                ):
                    buf = io.StringIO()
                    with mock.patch("sys.stdout", buf):
                        _mod.cmd_collect(None)
                    data = json.loads(buf.getvalue())
                    # Remove all path-dependent and time-dependent volatile fields
                    if "quota" in data:
                        data["quota"].pop("file_age_s", None)
                        data["quota"].pop("file_mtime", None)
                        data["quota"].pop("inner_age_s", None)
                        data["quota"].pop("path", None)  # temp dir path differs per call
                        data["quota"].pop("stale_threshold_s", None)
                    if "traces" in data:
                        data["traces"].pop("trace_file", None)  # temp dir path differs
                    if "git" in data:
                        for repo in data["git"].values():
                            repo.pop("dirty_file_count", None)  # changes if new files created
                    return data

        s1 = _snap()
        s2 = _snap()
        assert s1 == s2


# ---------------------------------------------------------------------------
# 3. diff_fixture_snapshots
# ---------------------------------------------------------------------------


class TestDiffFixtureSnapshots:
    """Verify specific markdown lines appear in diff output."""

    def _make_snap(
        self,
        count_24h: int = 10,
        failure_count_24h: int = 1,
        latency_p50_24h: float = 200.0,
        latency_p95_24h: float = 800.0,
        tokens_24h: int = 5000,
        dirty_files_odysseus: int = 0,
        quota_stale: bool = False,
        health_reachable: bool = True,
        health_healthy: bool = True,
        consecutive_failures: int = 0,
        snapshot_ts: str = "2026-06-11T00:00:00.000+00:00",
    ) -> Dict[str, Any]:
        success_count = count_24h - failure_count_24h
        success_rate = round(success_count / count_24h, 4) if count_24h else None
        return {
            "schema_version": "1",
            "snapshot_ts": snapshot_ts,
            "traces": {
                "trace_file": "/fake/traces.jsonl",
                "trace_file_exists": True,
                "trace_total_lines": count_24h,
                "last_24h": {
                    "count": count_24h,
                    "success_count": success_count,
                    "failure_count": failure_count_24h,
                    "success_rate": success_rate,
                    "latency_ms_p50": latency_p50_24h,
                    "latency_ms_p95": latency_p95_24h,
                    "total_tokens": tokens_24h,
                    "failures_by_classification": {},
                    "by_classification_model": [
                        {"classification": "code", "model_used": "m1", "count": count_24h, "tokens": tokens_24h, "failures": failure_count_24h}
                    ],
                },
                "last_7d": {
                    "count": count_24h,
                    "success_count": success_count,
                    "failure_count": failure_count_24h,
                    "success_rate": success_rate,
                    "latency_ms_p50": latency_p50_24h,
                    "latency_ms_p95": latency_p95_24h,
                    "total_tokens": tokens_24h,
                    "failures_by_classification": {},
                    "by_classification_model": [],
                },
            },
            "quota": {
                "path": "/fake/quota-live.json",
                "exists": not quota_stale,
                "file_mtime": 1749600000.0,
                "file_age_s": 100.0 if not quota_stale else 1200.0,
                "is_stale": quota_stale,
                "stale_threshold_s": 600,
                "data": None,
            },
            "health": {
                "reachable": health_reachable,
                "status_code": 200 if health_reachable else None,
                "data": {
                    "healthy": health_healthy,
                    "consecutive_failures": consecutive_failures,
                } if health_reachable else None,
            },
            "git": {
                "odysseus": {
                    "path": "/projects/odysseus",
                    "exists": True,
                    "branch": "main",
                    "dirty_file_count": dirty_files_odysseus,
                    "last_commit_subject": "Initial commit",
                    "last_commit_hash": "abc1234",
                    "error": None,
                },
                "platform": {
                    "path": "/projects/platform",
                    "exists": True,
                    "branch": "main",
                    "dirty_file_count": 2,
                    "last_commit_subject": "Initial commit",
                    "last_commit_hash": "def5678",
                    "error": None,
                },
            },
        }

    def _run_diff(self, snap_a: Dict, snap_b: Dict) -> str:
        """Write snapshots to temp files and capture diff stdout."""
        import io

        with tempfile.TemporaryDirectory() as tmp:
            a_path = os.path.join(tmp, "snap_a.json")
            b_path = os.path.join(tmp, "snap_b.json")
            with open(a_path, "w") as f:
                json.dump(snap_a, f)
            with open(b_path, "w") as f:
                json.dump(snap_b, f)
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                cmd_diff(a_path, b_path)
            return buf.getvalue()

    def test_failure_rate_worsened(self):
        a = self._make_snap(count_24h=10, failure_count_24h=1)  # SR=0.9
        b = self._make_snap(count_24h=10, failure_count_24h=3)  # SR=0.7
        output = self._run_diff(a, b)
        assert "worsened" in output
        assert "success_rate" in output

    def test_failure_rate_improved(self):
        a = self._make_snap(count_24h=10, failure_count_24h=5)  # SR=0.5
        b = self._make_snap(count_24h=10, failure_count_24h=1)  # SR=0.9
        output = self._run_diff(a, b)
        assert "improved" in output
        assert "success_rate" in output

    def test_latency_worsened(self):
        a = self._make_snap(latency_p95_24h=500.0)
        b = self._make_snap(latency_p95_24h=900.0)
        output = self._run_diff(a, b)
        assert "latency_ms_p95" in output
        assert "worsened" in output

    def test_latency_improved(self):
        a = self._make_snap(latency_p50_24h=800.0)
        b = self._make_snap(latency_p50_24h=200.0)
        output = self._run_diff(a, b)
        assert "latency_ms_p50" in output
        assert "improved" in output

    def test_dirty_files_worsened(self):
        a = self._make_snap(dirty_files_odysseus=0)
        b = self._make_snap(dirty_files_odysseus=5)
        output = self._run_diff(a, b)
        assert "odysseus dirty_file_count" in output
        assert "worsened" in output

    def test_dirty_files_improved(self):
        a = self._make_snap(dirty_files_odysseus=10)
        b = self._make_snap(dirty_files_odysseus=0)
        output = self._run_diff(a, b)
        assert "odysseus dirty_file_count" in output
        assert "improved" in output

    def test_quota_goes_stale(self):
        a = self._make_snap(quota_stale=False)
        b = self._make_snap(quota_stale=True)
        output = self._run_diff(a, b)
        assert "stale" in output
        assert "worsened" in output

    def test_quota_becomes_fresh(self):
        a = self._make_snap(quota_stale=True)
        b = self._make_snap(quota_stale=False)
        output = self._run_diff(a, b)
        assert "stale" in output
        assert "improved" in output

    def test_health_endpoint_goes_down(self):
        a = self._make_snap(health_reachable=True)
        b = self._make_snap(health_reachable=False)
        output = self._run_diff(a, b)
        assert "health endpoint" in output
        assert "worsened" in output

    def test_health_endpoint_comes_up(self):
        a = self._make_snap(health_reachable=False)
        b = self._make_snap(health_reachable=True)
        output = self._run_diff(a, b)
        assert "health endpoint" in output
        assert "improved" in output

    def test_no_change_no_false_alarm(self):
        a = self._make_snap()
        b = self._make_snap()
        output = self._run_diff(a, b)
        # Should not report any worsening
        assert "worsened" not in output

    def test_output_starts_with_header(self):
        a = self._make_snap()
        b = self._make_snap()
        output = self._run_diff(a, b)
        assert output.startswith("# Agent Audit Diff")

    def test_snapshot_ts_shown(self):
        a = self._make_snap(snapshot_ts="2026-06-10T00:00:00.000+00:00")
        b = self._make_snap(snapshot_ts="2026-06-11T00:00:00.000+00:00")
        output = self._run_diff(a, b)
        assert "2026-06-10" in output
        assert "2026-06-11" in output

    def test_new_classification_reported(self):
        a = self._make_snap()
        b = self._make_snap()
        # Inject a new classification into b only
        b["traces"]["last_7d"]["by_classification_model"].append(
            {"classification": "analysis", "model_used": "m3", "count": 2, "tokens": 400, "failures": 0}
        )
        output = self._run_diff(a, b)
        assert "analysis" in output
        assert "New classifications" in output

    def test_exit_code_always_zero(self):
        """diff exits 0 regardless of content."""
        a = self._make_snap()
        b = self._make_snap(failure_count_24h=9)  # drastic failure
        with tempfile.TemporaryDirectory() as tmp:
            a_path = os.path.join(tmp, "snap_a.json")
            b_path = os.path.join(tmp, "snap_b.json")
            with open(a_path, "w") as f:
                json.dump(a, f)
            with open(b_path, "w") as f:
                json.dump(b, f)
            # cmd_diff should not raise SystemExit
            import io
            buf = io.StringIO()
            with mock.patch("sys.stdout", buf):
                cmd_diff(a_path, b_path)  # no exception = exit 0 behaviour
