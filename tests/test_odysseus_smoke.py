"""tests/test_odysseus_smoke.py — unit tests for the odysseus-smoke harness.

All HTTP is mocked. These tests verify:
  - SSE delta parsing (thinking vs visible content)
  - empty-response detection
  - the "reasoning-model-in-agent-mode" fail reason
  - exit codes (0=all pass, 1=any fail)
  - JSONL receipt shape

Run:
    cd ~/projects/odysseus && python3 -m pytest tests/test_odysseus_smoke.py
"""

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Import the smoke script as a module (no .py extension).
# ---------------------------------------------------------------------------

import importlib.util
import importlib.machinery

_SMOKE_PATH = Path(__file__).parent.parent / "scripts" / "odysseus-smoke"


def _import_smoke():
    loader = importlib.machinery.SourceFileLoader("odysseus_smoke", str(_SMOKE_PATH))
    spec = importlib.util.spec_from_loader("odysseus_smoke", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


smoke = _import_smoke()


# ---------------------------------------------------------------------------
# Helpers for building fake SSE text
# ---------------------------------------------------------------------------


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _sse_done() -> str:
    return "data: [DONE]\n\n"


def _sse_event_error(msg: str) -> str:
    return f"event: error\ndata: {json.dumps({'error': msg})}\n\n"


def _run(coro):
    """Run an async coroutine in a new event loop (works without pytest-asyncio)."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# parse_sse_chunks
# ---------------------------------------------------------------------------


class TestParseSseChunks:
    def test_plain_delta(self):
        raw = _sse({"delta": "hello"}) + _sse_done()
        parsed = list(smoke.parse_sse_chunks(raw))
        data_payloads = [d for _, d in parsed if isinstance(d, dict)]
        assert any(d.get("delta") == "hello" for d in data_payloads)

    def test_done_sentinel(self):
        raw = _sse_done()
        parsed = list(smoke.parse_sse_chunks(raw))
        assert any(d == "[DONE]" for _, d in parsed)

    def test_event_error(self):
        raw = _sse_event_error("upstream down")
        parsed = list(smoke.parse_sse_chunks(raw))
        event_types = [et for et, _ in parsed]
        assert "error" in event_types

    def test_thinking_delta_flagged(self):
        raw = _sse({"delta": "reasoning...", "thinking": True}) + _sse_done()
        parsed = list(smoke.parse_sse_chunks(raw))
        thinking_items = [d for _, d in parsed if isinstance(d, dict) and d.get("thinking")]
        assert len(thinking_items) == 1

    def test_mixed_deltas(self):
        raw = (
            _sse({"delta": "<think>hidden</think>", "thinking": True})
            + _sse({"delta": "visible answer"})
            + _sse_done()
        )
        parsed = list(smoke.parse_sse_chunks(raw))
        dicts = [d for _, d in parsed if isinstance(d, dict)]
        thinking = [d for d in dicts if d.get("thinking")]
        visible = [d for d in dicts if "delta" in d and not d.get("thinking")]
        assert len(thinking) == 1
        assert len(visible) == 1
        assert visible[0]["delta"] == "visible answer"


# ---------------------------------------------------------------------------
# visible_delta_from_stream
# ---------------------------------------------------------------------------


class TestVisibleDeltaFromStream:
    def test_only_visible_deltas(self):
        raw = _sse({"delta": "hello "}) + _sse({"delta": "world"}) + _sse_done()
        assert smoke.visible_delta_from_stream(raw) == "hello world"

    def test_thinking_excluded(self):
        raw = (
            _sse({"delta": "thinking content", "thinking": True})
            + _sse({"delta": "real answer"})
            + _sse_done()
        )
        assert smoke.visible_delta_from_stream(raw) == "real answer"

    def test_empty_stream(self):
        raw = _sse_done()
        assert smoke.visible_delta_from_stream(raw) == ""

    def test_only_thinking_no_visible(self):
        raw = (
            _sse({"delta": "step 1", "thinking": True})
            + _sse({"delta": "step 2", "thinking": True})
            + _sse_done()
        )
        assert smoke.visible_delta_from_stream(raw) == ""

    def test_non_delta_events_ignored(self):
        raw = (
            _sse({"type": "model_info", "model": "MiniMax-M3"})
            + _sse({"delta": "answer"})
            + _sse_done()
        )
        assert smoke.visible_delta_from_stream(raw) == "answer"


# ---------------------------------------------------------------------------
# any_thinking_only
# ---------------------------------------------------------------------------


class TestAnyThinkingOnly:
    def test_thinking_only_returns_true(self):
        raw = _sse({"delta": "think", "thinking": True}) + _sse_done()
        assert smoke.any_thinking_only(raw) is True

    def test_visible_present_returns_false(self):
        raw = (
            _sse({"delta": "think", "thinking": True})
            + _sse({"delta": "answer"})
            + _sse_done()
        )
        assert smoke.any_thinking_only(raw) is False

    def test_no_deltas_returns_false(self):
        raw = _sse({"type": "model_info"}) + _sse_done()
        assert smoke.any_thinking_only(raw) is False

    def test_only_visible_no_thinking(self):
        raw = _sse({"delta": "hello"}) + _sse_done()
        assert smoke.any_thinking_only(raw) is False


# ---------------------------------------------------------------------------
# check_health (mocked HTTP)
# ---------------------------------------------------------------------------


class TestCheckHealth:
    def test_pass_when_healthy(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"healthy": True, "streak": 0}

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.get = AsyncMock(return_value=mock_resp)
            result = _run(smoke.check_health(timeout=5.0))

        assert result.status == "pass"
        assert result.latency_ms >= 0

    def test_fail_when_unhealthy(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"healthy": False, "reason": "quota stale"}

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.get = AsyncMock(return_value=mock_resp)
            result = _run(smoke.check_health(timeout=5.0))

        assert result.status == "fail"
        assert "false" in result.reason.lower()

    def test_fail_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.get = AsyncMock(return_value=mock_resp)
            result = _run(smoke.check_health(timeout=5.0))

        assert result.status == "fail"
        assert "503" in result.reason

    def test_fail_on_connection_error(self):
        import httpx

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.get = AsyncMock(
                side_effect=httpx.ConnectError("Connection refused")
            )
            result = _run(smoke.check_health(timeout=5.0))

        assert result.status == "fail"


# ---------------------------------------------------------------------------
# check_route_chat (mocked HTTP)
# ---------------------------------------------------------------------------


class TestCheckRouteChat:
    def test_pass_with_non_empty_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": "SMOKE OK",
            "model_used": "MiniMax-M3",
            "tokens": 5,
            "classification": "chat",
        }

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.post = AsyncMock(return_value=mock_resp)
            result = _run(smoke.check_route_chat(timeout=10.0))

        assert result.status == "pass"

    def test_fail_with_empty_response(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": "",
            "model_used": "MiniMax-M3",
        }

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.post = AsyncMock(return_value=mock_resp)
            result = _run(smoke.check_route_chat(timeout=10.0))

        assert result.status == "fail"
        assert "empty" in result.reason.lower()

    def test_fail_with_error_field(self):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "response": "",
            "error": True,
            "error_detail": "upstream down",
        }

        with patch("httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=MockClient.return_value)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            MockClient.return_value.post = AsyncMock(return_value=mock_resp)
            result = _run(smoke.check_route_chat(timeout=10.0))

        assert result.status == "fail"
        assert "error" in result.reason.lower()


# ---------------------------------------------------------------------------
# _e2e_chat_check — the agent/chat mode check
# ---------------------------------------------------------------------------


def _make_mock_stream_context(sse_text: str, status_code: int = 200):
    """Build a context-manager mock whose .iter_text() yields the SSE text."""
    mock_stream_ctx = MagicMock()
    mock_stream_ctx.__enter__ = MagicMock(return_value=mock_stream_ctx)
    mock_stream_ctx.__exit__ = MagicMock(return_value=False)
    mock_stream_ctx.status_code = status_code
    mock_stream_ctx.iter_text = MagicMock(return_value=iter([sse_text]))
    mock_stream_ctx.read = MagicMock(return_value=b"error")
    return mock_stream_ctx


def _make_client(sse_text: str, session_id: str = "test-session-id"):
    """Patch httpx.Client so session create/delete/stream are all mocked."""
    mock_stream_ctx = _make_mock_stream_context(sse_text)
    mock_client_instance = MagicMock()
    mock_client_instance.post.return_value = MagicMock(
        status_code=200,
        json=MagicMock(return_value={"id": session_id}),
    )
    mock_client_instance.delete.return_value = MagicMock(status_code=200)
    mock_client_instance.stream.return_value = mock_stream_ctx
    mock_client_instance.__enter__ = MagicMock(return_value=mock_client_instance)
    mock_client_instance.__exit__ = MagicMock(return_value=False)
    return mock_client_instance


class TestE2eChatCheck:
    """Tests for _e2e_chat_check (both chat and agent modes)."""

    def test_chat_mode_pass_with_visible_delta(self):
        sse = (
            _sse({"type": "model_info", "model": "MiniMax-M3"})
            + _sse({"delta": "SMOKE OK"})
            + _sse_done()
        )
        client = _make_client(sse)
        with patch("httpx.Client", return_value=client):
            result = _run(smoke._e2e_chat_check("chat_mode_e2e", "chat", timeout=30.0))
        assert result.status == "pass"
        assert "SMOKE OK" in result.reason

    def test_agent_mode_fail_thinking_only(self):
        """The MiniMax-M3 + agent mode bug: only thinking deltas, no visible output."""
        sse = (
            _sse({"type": "model_info", "model": "MiniMax-M3"})
            + _sse({"delta": "thinking step 1", "thinking": True})
            + _sse({"delta": "thinking step 2", "thinking": True})
            + _sse_done()
        )
        client = _make_client(sse)
        with patch("httpx.Client", return_value=client):
            result = _run(smoke._e2e_chat_check("agent_mode_e2e", "agent", timeout=30.0))
        assert result.status == "fail"
        assert "reasoning-model-in-agent-mode" in result.reason.lower()
        assert "no visible" in result.reason.lower()

    def test_agent_mode_fail_inline_think_tags_only(self):
        """Reasoning leaked as inline <think> text in plain deltas is not a visible answer."""
        sse = (
            _sse({"type": "model_info", "model": "MiniMax-M3"})
            + _sse({"delta": "<think>\nThe user is asking me to reply"})
            + _sse({"delta": " with exactly SMOKE OK..."})
            + _sse_done()
        )
        client = _make_client(sse)
        with patch("httpx.Client", return_value=client):
            result = _run(smoke._e2e_chat_check("agent_mode_e2e", "agent", timeout=30.0))
        assert result.status == "fail"
        assert "reasoning-model-in-agent-mode" in result.reason.lower()

    def test_inline_think_followed_by_visible_passes(self):
        """A closed <think> block followed by real text is a legitimate answer."""
        sse = (
            _sse({"delta": "<think>reasoning here</think>"})
            + _sse({"delta": "SMOKE OK"})
            + _sse_done()
        )
        client = _make_client(sse)
        with patch("httpx.Client", return_value=client):
            result = _run(smoke._e2e_chat_check("chat_mode_e2e", "chat", timeout=30.0))
        assert result.status == "pass"
        assert "SMOKE OK" in result.reason

    def test_agent_mode_fail_app_fallback_message(self):
        """The app's empty-response fallback string is a failure, not a visible reply."""
        sse = (
            _sse({"type": "model_info", "model": "MiniMax-M3"})
            + _sse({"delta": "thinking step 1", "thinking": True})
            + _sse({"delta": smoke.APP_EMPTY_RESPONSE_FALLBACK
                    + " Please try again or switch to a different model."})
            + _sse_done()
        )
        client = _make_client(sse)
        with patch("httpx.Client", return_value=client):
            result = _run(smoke._e2e_chat_check("agent_mode_e2e", "agent", timeout=30.0))
        assert result.status == "fail"
        assert "fallback" in result.reason.lower()

    def test_empty_stream_no_deltas(self):
        """Stream has no deltas at all (not even thinking)."""
        sse = (
            _sse({"type": "model_info", "model": "MiniMax-M3"})
            + _sse({"type": "metrics", "data": {}})
            + _sse_done()
        )
        client = _make_client(sse)
        with patch("httpx.Client", return_value=client):
            result = _run(smoke._e2e_chat_check("chat_mode_e2e", "chat", timeout=30.0))
        assert result.status == "fail"
        assert "no visible delta" in result.reason.lower()

    def test_thinking_plus_visible_passes(self):
        """Thinking deltas are fine as long as there is also a visible delta."""
        sse = (
            _sse({"delta": "let me think...", "thinking": True})
            + _sse({"delta": "SMOKE OK"})
            + _sse_done()
        )
        client = _make_client(sse)
        with patch("httpx.Client", return_value=client):
            result = _run(smoke._e2e_chat_check("agent_mode_e2e", "agent", timeout=30.0))
        assert result.status == "pass"

    def test_session_create_failure_fails_check(self):
        """If the session can't be created, the check should fail gracefully."""
        mock_client = MagicMock()
        mock_client.post.return_value = MagicMock(
            status_code=500,
            json=MagicMock(side_effect=Exception("bad response")),
        )
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        with patch("httpx.Client", return_value=mock_client):
            result = _run(smoke._e2e_chat_check("chat_mode_e2e", "chat", timeout=30.0))
        assert result.status == "fail"
        assert "session" in result.reason.lower()

    def test_http_error_on_stream_fails_check(self):
        """HTTP 503 on the chat_stream endpoint."""
        sse_ctx = _make_mock_stream_context("error body", status_code=503)
        mock_client = MagicMock()
        mock_client.post.return_value = MagicMock(
            status_code=200,
            json=MagicMock(return_value={"id": "sess-123"}),
        )
        mock_client.delete.return_value = MagicMock(status_code=200)
        mock_client.stream.return_value = sse_ctx
        mock_client.__enter__ = MagicMock(return_value=mock_client)
        mock_client.__exit__ = MagicMock(return_value=False)
        with patch("httpx.Client", return_value=mock_client):
            result = _run(smoke._e2e_chat_check("chat_mode_e2e", "chat", timeout=30.0))
        assert result.status == "fail"
        assert "503" in result.reason


# ---------------------------------------------------------------------------
# Exit code logic
# ---------------------------------------------------------------------------


class TestExitCodes:
    def _make_results(self, statuses):
        return [
            smoke.CheckResult(name=f"check_{i}", status=s, latency_ms=10.0)
            for i, s in enumerate(statuses)
        ]

    def test_all_pass_returns_0(self):
        results = self._make_results(["pass", "pass"])
        non_skipped = [r for r in results if r.status != "skipped"]
        ok = all(r.status == "pass" for r in non_skipped)
        assert ok is True

    def test_any_fail_returns_1(self):
        results = self._make_results(["pass", "fail", "pass"])
        non_skipped = [r for r in results if r.status != "skipped"]
        ok = all(r.status == "pass" for r in non_skipped)
        assert ok is False

    def test_all_skipped_is_pass(self):
        results = self._make_results(["skipped", "skipped"])
        non_skipped = [r for r in results if r.status != "skipped"]
        # all() on empty iterable is True — treated as pass
        ok = all(r.status == "pass" for r in non_skipped)
        assert ok is True

    def test_skipped_plus_pass_is_pass(self):
        results = self._make_results(["pass", "skipped"])
        non_skipped = [r for r in results if r.status != "skipped"]
        ok = all(r.status == "pass" for r in non_skipped)
        assert ok is True

    def test_skipped_plus_fail_is_fail(self):
        results = self._make_results(["skipped", "fail"])
        non_skipped = [r for r in results if r.status != "skipped"]
        ok = all(r.status == "pass" for r in non_skipped)
        assert ok is False


# ---------------------------------------------------------------------------
# JSONL receipt shape
# ---------------------------------------------------------------------------


class TestJsonlReceipt:
    def test_receipt_shape(self, tmp_path):
        """write_jsonl_receipt writes valid JSONL with expected keys."""
        results = [
            smoke.CheckResult(name="health", status="pass", latency_ms=42.1, reason="ok"),
            smoke.CheckResult(name="route_chat", status="fail", latency_ms=123.4, reason="empty"),
            smoke.CheckResult(
                name="chat_mode_e2e", status="skipped", latency_ms=0, reason="no endpoint"
            ),
        ]
        jsonl_path = tmp_path / "smoke.jsonl"
        original = smoke.SMOKE_JSONL
        smoke.SMOKE_JSONL = jsonl_path
        try:
            smoke.write_jsonl_receipt(results)
        finally:
            smoke.SMOKE_JSONL = original

        lines = jsonl_path.read_text().splitlines()
        assert len(lines) == 1

        receipt = json.loads(lines[0])
        assert "ts" in receipt
        assert isinstance(receipt["ts"], float)
        assert "checks" in receipt
        assert "overall" in receipt

        # overall is "fail" because route_chat failed
        assert receipt["overall"] == "fail"

        for name in ("health", "route_chat", "chat_mode_e2e"):
            assert name in receipt["checks"]
            check = receipt["checks"][name]
            assert "status" in check
            assert "latency_ms" in check
            assert "reason" in check

    def test_receipt_appends_multiple_runs(self, tmp_path):
        results = [smoke.CheckResult(name="health", status="pass", latency_ms=10.0)]
        jsonl_path = tmp_path / "smoke.jsonl"
        original = smoke.SMOKE_JSONL
        smoke.SMOKE_JSONL = jsonl_path
        try:
            smoke.write_jsonl_receipt(results)
            smoke.write_jsonl_receipt(results)
        finally:
            smoke.SMOKE_JSONL = original

        lines = jsonl_path.read_text().splitlines()
        assert len(lines) == 2

    def test_receipt_overall_pass(self, tmp_path):
        results = [
            smoke.CheckResult(name="health", status="pass", latency_ms=10.0),
            smoke.CheckResult(name="route_chat", status="skipped", latency_ms=0.0),
        ]
        jsonl_path = tmp_path / "smoke.jsonl"
        original = smoke.SMOKE_JSONL
        smoke.SMOKE_JSONL = jsonl_path
        try:
            smoke.write_jsonl_receipt(results)
        finally:
            smoke.SMOKE_JSONL = original

        receipt = json.loads(jsonl_path.read_text().strip())
        assert receipt["overall"] == "pass"
