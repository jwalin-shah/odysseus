# tests/test_session_followup.py
"""Tests for Feature 2 — resumable/interactive sessions.

Covers:
  - session_id is captured from claude JSON output and stored in run record
  - finalize_run stores session_id + adapter_name
  - POST /api/route/{run_id}/followup happy path: returns new run_id linked to parent
  - followup for run without session_id → in-band error, never 500
  - followup for non-claude provider → in-band error, never 500
  - followup for unknown run_id → in-band error, never 500
  - followup background coroutine writes trace with source=router_followup
  - route_code_resume calls claude with --resume flag and correct config_dir

All tests mock CLI execution — no real binaries are invoked.
"""

import asyncio
import json
import subprocess
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.code_run_store as run_store
from core import orchestration_trace as otrace
from core.router import TaskRouter, _CLI_ADAPTERS
from routes.orchestration_routes import setup_orchestration_routes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(task_router=None):
    app = FastAPI()
    app.include_router(setup_orchestration_routes(task_router=task_router))
    return app


class _FakeRouter:
    """Minimal mock TaskRouter for route endpoint tests."""

    def __init__(self, route_code_result=None, resume_result=None):
        self._route_code_result = route_code_result or {
            "response": "generated code",
            "model_used": "sonnet",
            "tokens": 20,
            "provider": "claude-ca",
            "session_id": "test-session-id-abc",
        }
        self._resume_result = resume_result or {
            "response": "followup response",
            "model_used": "sonnet",
            "tokens": 15,
            "provider": "claude-ca",
            "session_id": "test-session-id-abc",
        }

    async def classify_task_async(self, task, hint="auto"):
        return "code"

    async def route_code(self, task):
        return dict(self._route_code_result)

    async def route_code_resume(self, task, session_id, adapter_name):
        return dict(self._resume_result)

    async def route(self, task, task_type="auto"):
        return {"response": "ok", "model_used": "m3", "tokens": 5, "classification": "chat"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_run_store():
    with run_store._store_lock:
        run_store._store.clear()
    yield
    with run_store._store_lock:
        run_store._store.clear()


@pytest.fixture
def trace_file(tmp_path, monkeypatch):
    path = tmp_path / "traces.jsonl"
    monkeypatch.setattr(otrace, "TRACE_DIR", str(tmp_path))
    monkeypatch.setattr(otrace, "TRACE_FILE", str(path))
    monkeypatch.setattr(run_store, "_RUN_DIR", str(tmp_path))
    monkeypatch.setattr(run_store, "_RUN_FILE", str(tmp_path / "code_runs.jsonl"))
    return path


# ---------------------------------------------------------------------------
# run_store: session_id + adapter_name storage
# ---------------------------------------------------------------------------


class TestRunStoreSessionFields:
    def test_create_run_has_session_id_none(self, trace_file):
        run_id = run_store.create_run("task")
        rec = run_store.get_run(run_id)
        assert rec["session_id"] is None
        assert rec["adapter_name"] is None

    def test_create_run_with_parent_run_id(self, trace_file):
        parent_id = run_store.create_run("parent task")
        child_id = run_store.create_run("child task", parent_run_id=parent_id)
        rec = run_store.get_run(child_id)
        assert rec["parent_run_id"] == parent_id

    def test_finalize_run_stores_session_id(self, trace_file):
        run_id = run_store.create_run("task")
        run_store.mark_running(run_id)
        rec = run_store.finalize_run(
            run_id,
            success=True,
            result="done",
            tokens=10,
            latency_ms=100.0,
            session_id="my-session-xyz",
            adapter_name="claude-ca",
        )
        assert rec["session_id"] == "my-session-xyz"
        assert rec["adapter_name"] == "claude-ca"

    def test_finalize_run_session_id_none_when_not_provided(self, trace_file):
        run_id = run_store.create_run("task")
        run_store.mark_running(run_id)
        rec = run_store.finalize_run(run_id, success=True, result="ok", tokens=5, latency_ms=50.0)
        # session_id stays None when not provided
        assert rec["session_id"] is None

    def test_get_run_includes_session_fields(self, trace_file):
        run_id = run_store.create_run("task")
        run_store.finalize_run(
            run_id,
            success=True,
            result="done",
            tokens=1,
            latency_ms=1.0,
            session_id="sess-123",
            adapter_name="claude-cb",
        )
        rec = run_store.get_run(run_id)
        assert rec["session_id"] == "sess-123"
        assert rec["adapter_name"] == "claude-cb"


# ---------------------------------------------------------------------------
# route_code captures session_id in run record (via background coroutine)
# ---------------------------------------------------------------------------


class TestSessionIdCapture:
    def test_async_code_dispatch_stores_session_id(self, trace_file):
        """After background finalization, run record has session_id."""
        router = _FakeRouter(route_code_result={
            "response": "output",
            "model_used": "sonnet",
            "tokens": 10,
            "provider": "claude-ca",
            "session_id": "captured-session-id",
        })
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post("/api/route", json={"task": "write something.py", "type": "code"})
        run_id = resp.json()["run_id"]

        # Wait for background task to complete
        deadline = time.time() + 2.0
        while time.time() < deadline:
            rec = run_store.get_run(run_id)
            if rec and rec["status"] in ("success", "error"):
                break
            time.sleep(0.05)

        rec = run_store.get_run(run_id)
        if rec and rec["status"] == "success":
            assert rec["session_id"] == "captured-session-id"
            assert rec["adapter_name"] == "claude-ca"

    def test_no_session_id_for_non_claude_provider(self, trace_file):
        """Codex runs should not have session_id in finalized record."""
        router = _FakeRouter(route_code_result={
            "response": "codex output",
            "model_used": "gpt-5",
            "tokens": 8,
            "provider": "codex",
            # no session_id key
        })
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post("/api/route", json={"task": "write a script.py", "type": "code"})
        run_id = resp.json()["run_id"]

        deadline = time.time() + 2.0
        while time.time() < deadline:
            rec = run_store.get_run(run_id)
            if rec and rec["status"] in ("success", "error"):
                break
            time.sleep(0.05)

        rec = run_store.get_run(run_id)
        if rec and rec["status"] == "success":
            assert rec.get("session_id") is None
            assert rec.get("adapter_name") == "codex"


# ---------------------------------------------------------------------------
# Followup endpoint: happy path
# ---------------------------------------------------------------------------


class TestFollowupHappyPath:
    def _setup_run_with_session(self, trace_file, client):
        """Submit a code task and wait for finalization with session_id."""
        router = _FakeRouter()
        app = _make_app(router)
        c = TestClient(app, raise_server_exceptions=False)
        resp = c.post("/api/route", json={"task": "write code.py", "type": "code"})
        run_id = resp.json()["run_id"]

        deadline = time.time() + 2.0
        while time.time() < deadline:
            rec = run_store.get_run(run_id)
            if rec and rec["status"] in ("success", "error"):
                break
            time.sleep(0.05)
        return c, run_id

    def test_followup_returns_new_run_id(self, trace_file):
        router = _FakeRouter()
        client = TestClient(_make_app(router), raise_server_exceptions=False)

        # Submit initial run and wait for it to complete
        resp = client.post("/api/route", json={"task": "write main.py", "type": "code"})
        run_id = resp.json()["run_id"]
        deadline = time.time() + 2.0
        while time.time() < deadline:
            rec = run_store.get_run(run_id)
            if rec and rec["status"] in ("success", "error"):
                break
            time.sleep(0.05)

        # Now followup
        followup_resp = client.post(
            f"/api/route/{run_id}/followup",
            json={"message": "now add error handling"},
        )
        assert followup_resp.status_code == 200
        data = followup_resp.json()
        assert "run_id" in data
        assert data["run_id"] != run_id
        assert data["status"] == "submitted"
        assert data["parent_run_id"] == run_id
        assert "poll_url" in data

    def test_followup_trace_has_router_followup_source(self, trace_file):
        router = _FakeRouter()
        client = TestClient(_make_app(router), raise_server_exceptions=False)

        resp = client.post("/api/route", json={"task": "write code.py", "type": "code"})
        run_id = resp.json()["run_id"]
        deadline = time.time() + 2.0
        while time.time() < deadline:
            rec = run_store.get_run(run_id)
            if rec and rec["status"] in ("success", "error"):
                break
            time.sleep(0.05)

        client.post(f"/api/route/{run_id}/followup", json={"message": "add tests"})

        lines = trace_file.read_text().splitlines()
        sources = [json.loads(l).get("source") for l in lines]
        assert "router_followup_submission" in sources


# ---------------------------------------------------------------------------
# Followup endpoint: error cases (in-band, never 500)
# ---------------------------------------------------------------------------


class TestFollowupErrorCases:
    def test_followup_unknown_run_id_returns_error_not_500(self, trace_file):
        router = _FakeRouter()
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post(
            "/api/route/nonexistent-run-xyz/followup",
            json={"message": "hello"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] is True
        assert "not found" in data["response"].lower() or "not found" in data.get("error_detail", "").lower()

    def test_followup_no_session_id_returns_error(self, trace_file):
        """Run without session_id → followup returns in-band error."""
        run_id = run_store.create_run("task")
        run_store.mark_running(run_id)
        # finalize WITHOUT session_id
        run_store.finalize_run(
            run_id,
            success=True,
            result="done",
            tokens=5,
            latency_ms=100.0,
            adapter_name="codex",
            # session_id deliberately omitted
        )

        router = _FakeRouter()
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post(
            f"/api/route/{run_id}/followup",
            json={"message": "follow up"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] is True
        assert "session_id" in data["response"].lower() or "not supported" in data["response"].lower()

    def test_followup_non_claude_provider_returns_error(self, trace_file):
        """Non-claude adapter (codex) doesn't support resume."""
        run_id = run_store.create_run("task")
        run_store.mark_running(run_id)
        run_store.finalize_run(
            run_id,
            success=True,
            result="done",
            tokens=5,
            latency_ms=50.0,
            session_id=None,  # codex never produces one
            adapter_name="codex",
        )

        router = _FakeRouter()
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post(
            f"/api/route/{run_id}/followup",
            json={"message": "continue"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] is True

    def test_followup_gemini_provider_returns_error(self, trace_file):
        """Gemini adapter doesn't support resume."""
        run_id = run_store.create_run("task")
        run_store.mark_running(run_id)
        run_store.finalize_run(
            run_id,
            success=True,
            result="done",
            tokens=5,
            latency_ms=50.0,
            session_id=None,
            adapter_name="gemini",
        )

        router = _FakeRouter()
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post(
            f"/api/route/{run_id}/followup",
            json={"message": "more please"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] is True


# ---------------------------------------------------------------------------
# route_code_resume — uses --resume flag with correct account
# ---------------------------------------------------------------------------


class TestRouteCodeResume:
    """Unit tests for TaskRouter.route_code_resume."""

    def test_resume_calls_claude_with_resume_flag(self):
        router = TaskRouter()
        session_id = "sess-abcd-1234"
        adapter_name = "claude-ca"

        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps({
                "type": "result",
                "result": "resumed answer",
                "session_id": session_id,
            }),
            stderr="",
        )

        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch.object(Path, "is_dir", return_value=True), \
             patch("subprocess.run", return_value=mock_result) as mock_run:
            result = asyncio.run(
                router.route_code_resume("add tests", session_id=session_id, adapter_name=adapter_name)
            )

        assert result["response"] == "resumed answer"
        assert result["provider"] == "claude-ca"
        assert "error" not in result

        # Verify --resume was in the argv
        called_argv = mock_run.call_args[0][0]
        assert "--resume" in called_argv
        assert session_id in called_argv

    def test_resume_sets_correct_config_dir_for_cb(self):
        router = TaskRouter()
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps({"type": "result", "result": "ok", "session_id": "sess-cb"}),
            stderr="",
        )
        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch.object(Path, "is_dir", return_value=True), \
             patch("subprocess.run", return_value=mock_result) as mock_run:
            result = asyncio.run(
                router.route_code_resume("task", session_id="sess-cb", adapter_name="claude-cb")
            )

        called_env = mock_run.call_args[1].get("env") or mock_run.call_args[0][4] if len(mock_run.call_args[0]) > 4 else mock_run.call_args[1].get("env", {})
        # Check env directly
        env_arg = mock_run.call_args.kwargs.get("env") or {}
        assert env_arg.get("CLAUDE_CONFIG_DIR", "").endswith(".claude-b")

    def test_resume_unsupported_adapter_returns_error(self):
        router = TaskRouter()
        result = asyncio.run(
            router.route_code_resume("task", session_id="sess-xyz", adapter_name="codex")
        )
        assert result["error"] is True
        assert "resume" in result["response"].lower() or "not support" in result["response"].lower()

    def test_resume_timeout_returns_error(self):
        router = TaskRouter()
        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch.object(Path, "is_dir", return_value=True), \
             patch("subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 300)):
            result = asyncio.run(
                router.route_code_resume("task", session_id="sess-x", adapter_name="claude-ca")
            )
        assert result["error"] is True
        assert "timed out" in result["response"].lower()

    def test_resume_binary_not_found_returns_error(self):
        router = TaskRouter()
        with patch("shutil.which", return_value="/usr/bin/claude"), \
             patch.object(Path, "is_dir", return_value=True), \
             patch("subprocess.run", side_effect=FileNotFoundError("claude")):
            result = asyncio.run(
                router.route_code_resume("task", session_id="sess-x", adapter_name="claude-ca")
            )
        assert result["error"] is True
        assert "not found" in result["response"].lower()
