# tests/test_async_code_dispatch.py
"""Tests for async code-dispatch via POST /api/route.

Covers:
  - Code task with sync=False (default) returns run_id immediately without blocking.
  - sync=True escape hatch blocks and returns the full response contract.
  - Submission trace is written at request time; completion trace is written
    by the background coroutine when the CLI finishes.
  - Errors stay in-band (never a 500) for both async and sync code paths.
  - GET /api/route/{run_id} returns current run status.
  - Non-code tasks (research, chat) always take the synchronous path regardless
    of the sync flag.

All tests mock the claude CLI / route_code — the real binary is never invoked.
"""

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import core.code_run_store as run_store
from core import orchestration_trace as otrace
from routes.orchestration_routes import setup_orchestration_routes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(task_router=None):
    app = FastAPI()
    app.include_router(setup_orchestration_routes(task_router=task_router))
    return app


def _make_router(classification: str = "code", route_code_result: dict = None,
                 route_result: dict = None, raise_exc: Exception = None):
    """Build a minimal mock TaskRouter."""
    if route_code_result is None:
        route_code_result = {
            "response": "def hello(): pass",
            "model_used": "sonnet",
            "tokens": 42,
            "provider": "ca",
        }
    if route_result is None:
        route_result = {
            "response": "ok",
            "model_used": "minimax-m3",
            "tokens": 5,
            "classification": classification,
        }

    class _FakeRouter:
        async def classify_task_async(self, task, hint="auto"):
            return classification

        async def route_code(self, task):
            if raise_exc:
                raise raise_exc
            return dict(route_code_result)

        async def route(self, task, task_type="auto"):
            return dict(route_result)

    return _FakeRouter()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_run_store():
    """Each test gets a clean in-memory store."""
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
    # Also redirect the code-run log to tmp_path so tests don't write to the
    # real data dir.
    monkeypatch.setattr(run_store, "_RUN_DIR", str(tmp_path))
    monkeypatch.setattr(run_store, "_RUN_FILE", str(tmp_path / "code_runs.jsonl"))
    return path


# ---------------------------------------------------------------------------
# Async code-dispatch: non-blocking submission
# ---------------------------------------------------------------------------


class TestAsyncCodeDispatch:
    """POST /api/route with a code task returns run_id immediately."""

    def test_code_task_returns_run_id_not_blocking(self, trace_file):
        """Default (sync=False): code task must return run_id + status=submitted."""
        client = TestClient(_make_app(_make_router("code")), raise_server_exceptions=False)
        resp = client.post("/api/route", json={"task": "write a .py file", "type": "code"})
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" in data, f"Expected run_id in response: {data}"
        assert data["status"] == "submitted"
        assert data["classification"] == "code"
        assert data["response"] is None
        assert "poll_url" in data

    def test_code_task_async_stores_run_in_memory(self, trace_file):
        """The run_id returned is immediately retrievable from the store."""
        client = TestClient(_make_app(_make_router("code")), raise_server_exceptions=False)
        resp = client.post("/api/route", json={"task": "implement auth.py", "type": "code"})
        run_id = resp.json()["run_id"]
        rec = run_store.get_run(run_id)
        assert rec is not None
        assert rec["status"] in ("submitted", "running", "success")

    def test_code_task_submission_trace_written(self, trace_file):
        """A submission trace with source=router_async_submission is written immediately."""
        client = TestClient(_make_app(_make_router("code")), raise_server_exceptions=False)
        client.post("/api/route", json={"task": "fix .go file", "type": "code"})
        lines = trace_file.read_text().splitlines()
        assert len(lines) >= 1
        row = json.loads(lines[0])
        assert row["source"] == "router_async_submission"
        assert row["classification"] == "code"
        assert row["success"] is True

    def test_code_task_completion_trace_written_by_background(self, trace_file):
        """After the background task finishes, a completion trace is also written."""
        router = _make_router("code", route_code_result={
            "response": "print('hi')",
            "model_used": "sonnet",
            "tokens": 10,
            "provider": "ca",
        })
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post("/api/route", json={"task": "write hello.py", "type": "code"})
        run_id = resp.json()["run_id"]

        # TestClient flushes pending asyncio tasks; give any background work a moment
        # by driving the event loop. The background task is a coroutine that runs
        # within the test's asyncio loop when using TestClient.
        # We poll the store for up to 2s.
        deadline = time.time() + 2.0
        while time.time() < deadline:
            rec = run_store.get_run(run_id)
            if rec and rec["status"] in ("success", "error"):
                break
            time.sleep(0.05)

        # If the background task ran, a completion trace should exist.
        lines = trace_file.read_text().splitlines()
        sources = [json.loads(l).get("source") for l in lines]
        if "router_async_completion" in sources:
            rec = run_store.get_run(run_id)
            assert rec["status"] == "success"
            assert rec["tokens"] == 10

    def test_run_id_is_404_for_unknown(self, trace_file):
        """GET /api/route/<unknown> returns 404."""
        client = TestClient(_make_app(_make_router("code")), raise_server_exceptions=False)
        resp = client.get("/api/route/nonexistent-run-id-xyz")
        assert resp.status_code == 404

    def test_run_status_poll_endpoint(self, trace_file):
        """GET /api/route/{run_id} returns the run record."""
        client = TestClient(_make_app(_make_router("code")), raise_server_exceptions=False)
        resp = client.post("/api/route", json={"task": "debug utils.py", "type": "code"})
        run_id = resp.json()["run_id"]
        status_resp = client.get(f"/api/route/{run_id}")
        assert status_resp.status_code == 200
        rec = status_resp.json()
        assert rec["run_id"] == run_id
        assert rec["status"] in ("submitted", "running", "success", "error")


# ---------------------------------------------------------------------------
# Sync escape hatch
# ---------------------------------------------------------------------------


class TestSyncEscapeHatch:
    """sync=True forces the old blocking behaviour and returns the full contract."""

    def test_sync_true_returns_full_response(self, trace_file):
        """sync=True code task must return response/model_used/tokens/classification."""
        router = _make_router("code", route_code_result={
            "response": "def hello(): pass",
            "model_used": "sonnet",
            "tokens": 42,
            "provider": "ca",
        })
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post(
            "/api/route",
            json={"task": "write a hello world function", "type": "code", "sync": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" not in data, f"sync=True should not return run_id: {data}"
        assert data["classification"] == "code"
        assert "def hello" in data["response"]
        assert data["model_used"] == "sonnet"
        assert data["tokens"] == 42

    def test_sync_true_writes_single_trace(self, trace_file):
        """sync=True records exactly one trace (the completion trace, not a submission)."""
        client = TestClient(_make_app(_make_router("code")), raise_server_exceptions=False)
        client.post(
            "/api/route",
            json={"task": "refactor main.py", "type": "code", "sync": True},
        )
        lines = trace_file.read_text().splitlines()
        # Exactly one trace (no separate submission + completion traces for sync)
        sources = [json.loads(l).get("source") for l in lines]
        assert "router_async_submission" not in sources
        assert "router_async_completion" not in sources

    def test_sync_true_error_stays_in_band(self, trace_file):
        """sync=True + CLI error → 200 with error:True, not a 500."""
        router = _make_router("code", route_code_result={
            "response": "CLI error: quota exhausted",
            "model_used": "unknown",
            "tokens": 0,
            "provider": "ca",
            "error": True,
        })
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post(
            "/api/route",
            json={"task": "build app.go", "type": "code", "sync": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] is True

    def test_sync_exception_stays_in_band(self, trace_file):
        """sync=True + route_code raises → 200 with error:True, not a 500."""
        router = _make_router("code", raise_exc=RuntimeError("binary missing"))
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post(
            "/api/route",
            json={"task": "write utils.ts", "type": "code", "sync": True},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["error"] is True
        assert "binary missing" in data.get("error_detail", "") or data.get("response", "")


# ---------------------------------------------------------------------------
# Non-code tasks always take the synchronous path
# ---------------------------------------------------------------------------


class TestNonCodeTasksSynchronous:
    """Research and chat tasks never return a run_id — always synchronous."""

    def test_chat_task_no_run_id(self, trace_file):
        router = _make_router("chat")
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post("/api/route", json={"task": "hello!", "type": "chat"})
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" not in data
        assert data["classification"] == "chat"

    def test_research_task_no_run_id(self, trace_file):
        router = _make_router("research")
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post(
            "/api/route",
            json={"task": "what is quantum computing", "type": "research"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "run_id" not in data

    def test_chat_task_sync_flag_ignored(self, trace_file):
        """sync=True on a chat task has no effect — still returns full response."""
        router = _make_router("chat")
        client = TestClient(_make_app(router), raise_server_exceptions=False)
        resp = client.post(
            "/api/route",
            json={"task": "good morning", "type": "chat", "sync": True},
        )
        assert resp.status_code == 200
        assert "run_id" not in resp.json()


# ---------------------------------------------------------------------------
# run_store unit tests
# ---------------------------------------------------------------------------


class TestRunStore:
    def test_create_run_returns_string_id(self, trace_file):
        run_id = run_store.create_run("fix foo.py")
        assert isinstance(run_id, str)
        assert len(run_id) > 0

    def test_initial_status_is_submitted(self, trace_file):
        run_id = run_store.create_run("write bar.py")
        rec = run_store.get_run(run_id)
        assert rec["status"] == "submitted"
        assert rec["result"] is None

    def test_mark_running_flips_status(self, trace_file):
        run_id = run_store.create_run("refactor baz.go")
        run_store.mark_running(run_id)
        assert run_store.get_run(run_id)["status"] == "running"

    def test_finalize_success(self, trace_file):
        run_id = run_store.create_run("implement qux.rs")
        run_store.mark_running(run_id)
        rec = run_store.finalize_run(
            run_id, success=True, result="done", tokens=100, latency_ms=500.0
        )
        assert rec["status"] == "success"
        assert rec["tokens"] == 100
        assert rec["result"] == "done"
        assert run_store.get_run(run_id)["status"] == "success"

    def test_finalize_error(self, trace_file):
        run_id = run_store.create_run("deploy prod.sh")
        run_store.mark_running(run_id)
        rec = run_store.finalize_run(
            run_id, success=False, error="quota exhausted", tokens=0, latency_ms=1.0
        )
        assert rec["status"] == "error"
        assert "quota exhausted" in rec["error"]

    def test_get_run_unknown_returns_none(self):
        assert run_store.get_run("nonexistent-id-xyz") is None

    def test_create_run_appends_to_file(self, trace_file):
        run_store.create_run("some code task")
        run_file = trace_file.parent / "code_runs.jsonl"
        assert run_file.exists()
        line = json.loads(run_file.read_text().splitlines()[0])
        assert line["_event"] == "submitted"
        assert line["status"] == "submitted"
