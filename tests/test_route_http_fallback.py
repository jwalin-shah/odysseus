"""Tests for the HTTP fallback path in TaskRouter.

The fallback is the last-resort code dispatch when every CLI adapter
(claude-ca/cb/codex/gemini) is exhausted. It calls a configured free
model (default MiniMax M3) over HTTP and returns the same shape as
route_code.

These tests verify:
  * The fallback is invoked when select_adapter returns None.
  * The fallback is skipped when a CLI adapter is available.
  * A connection failure returns an in-band error (never raises).
  * A missing API key returns an in-band error.
"""

import asyncio
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from core.router import TaskRouter, _resolve_fallback_api_key


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


# ---------------------------------------------------------------------------
# select_adapter gating
# ---------------------------------------------------------------------------

class TestFallbackGating:
    def test_route_code_falls_through_when_no_adapter(self, monkeypatch):
        """When select_adapter returns None, route_code should call the
        HTTP fallback rather than returning a hard error."""
        # Force the fallback to a deterministic no-key error path so we
        # don't actually hit the network.
        monkeypatch.delenv("M3_FALLBACK_KEY", raising=False)
        monkeypatch.delenv("TOKENROUTER_API_KEY", raising=False)
        # Patch the key resolver to return None.
        with patch("core.router._resolve_fallback_api_key", return_value=None):
            r = TaskRouter()
            with patch.object(r, "select_adapter", return_value=None):
                result = _run(r.route_code("implement a hello world function"))
        assert result["error"] is True
        assert "TOKENROUTER_API_KEY" in result["response"] or "M3_FALLBACK_KEY" in result["response"]
        assert result["provider"] == "none"
        assert result["tokens"] == 0

    def test_route_code_skips_fallback_when_adapter_available(self, monkeypatch):
        """When a CLI adapter is available, route_code should use it
        and NEVER call the HTTP fallback."""
        called = {"fallback": False}
        adapter = {
            "name": "fake",
            "provider_key": "fake",
            "binary": "fake",
            "config_dir": None,
            "build_argv": lambda b, t, c: [b, t],
            "build_env": None,
            "is_exhausted": lambda d: False,
            "parse_output": lambda so, se, rc: ("fake response", None),
            "supports_resume": False,
        }
        fake_proc = MagicMock(returncode=0, stdout="hello", stderr="")
        r = TaskRouter()
        with patch.object(r, "select_adapter", return_value=adapter):
            with patch("subprocess.run", return_value=fake_proc):
                async def _fallback_should_not_run(task):
                    called["fallback"] = True
                    return {"error": True, "response": "should not happen"}
                with patch.object(r, "route_http_fallback", side_effect=_fallback_should_not_run):
                    result = _run(r.route_code("write a hello function"))
        assert called["fallback"] is False, "fallback should not be called when an adapter is available"
        # parse_output returns the hardcoded "fake response" tuple element
        assert result.get("response") == "fake response"
        assert result.get("provider") == "fake"


# ---------------------------------------------------------------------------
# route_http_fallback
# ---------------------------------------------------------------------------

class TestRouteHttpFallback:
    def test_missing_api_key_returns_inband_error(self, monkeypatch):
        monkeypatch.delenv("M3_FALLBACK_KEY", raising=False)
        monkeypatch.delenv("TOKENROUTER_API_KEY", raising=False)
        with patch("core.router._resolve_fallback_api_key", return_value=None):
            r = TaskRouter()
            result = _run(r.route_http_fallback("anything"))
        assert result["error"] is True
        assert "M3_FALLBACK_KEY" in result["response"] or "TOKENROUTER_API_KEY" in result["response"]
        assert result["provider"] == "none"

    def test_successful_http_call_returns_standard_shape(self, monkeypatch):
        """A successful HTTP call to the fallback endpoint should return
        the same shape as route_code."""
        monkeypatch.setenv("M3_FALLBACK_KEY", "fake-key")
        monkeypatch.setenv("M3_FALLBACK_URL", "https://example.test/v1/chat/completions")
        monkeypatch.setenv("M3_FALLBACK_MODEL", "fake-model")

        fake_response_body = json.dumps({
            "choices": [{"message": {"content": "def hello():\n    pass"}}],
            "usage": {"total_tokens": 17},
        }).encode("utf-8")
        fake_resp = MagicMock()
        fake_resp.read = MagicMock(return_value=fake_response_body)
        fake_resp.__enter__ = MagicMock(return_value=fake_resp)
        fake_resp.__exit__ = MagicMock(return_value=False)

        with patch("urllib.request.urlopen", return_value=fake_resp):
            r = TaskRouter()
            result = _run(r.route_http_fallback("write a hello function"))

        assert "error" not in result or not result.get("error")
        assert result["response"].startswith("def hello")
        assert result["model_used"] == "fake-model"
        assert result["provider"] == "http_fallback:fake-model"
        assert result["tokens"] == 17

    def test_url_error_returns_inband_error(self, monkeypatch):
        """A network failure should produce an in-band error, never raise."""
        import urllib.error
        monkeypatch.setenv("M3_FALLBACK_KEY", "fake-key")
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("connection refused")):
            r = TaskRouter()
            result = _run(r.route_http_fallback("anything"))
        assert result["error"] is True
        assert "HTTP fallback failed" in result["response"]
        assert result["tokens"] == 0

    def test_uses_default_url_and_model(self, monkeypatch):
        """When no env vars are set, the fallback should default to
        TokenRouter + MiniMax-M3."""
        monkeypatch.delenv("M3_FALLBACK_URL", raising=False)
        monkeypatch.delenv("M3_FALLBACK_MODEL", raising=False)
        monkeypatch.setenv("M3_FALLBACK_KEY", "fake-key")

        captured = {}
        def fake_urlopen(req, **kw):
            captured["url"] = req.full_url
            captured["body"] = json.loads(req.data)
            fake_resp = MagicMock()
            fake_resp.read = MagicMock(return_value=b'{"choices":[{"message":{"content":"ok"}}],"usage":{"total_tokens":1}}')
            fake_resp.__enter__ = MagicMock(return_value=fake_resp)
            fake_resp.__exit__ = MagicMock(return_value=False)
            return fake_resp

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            r = TaskRouter()
            _run(r.route_http_fallback("x"))

        assert "tokenrouter.com" in captured["url"]
        assert captured["body"]["model"] == "MiniMax-M3"


# ---------------------------------------------------------------------------
# _resolve_fallback_api_key
# ---------------------------------------------------------------------------

class TestResolveFallbackKey:
    def test_env_var_wins(self, monkeypatch):
        monkeypatch.setenv("M3_FALLBACK_KEY", "from-env")
        assert _resolve_fallback_api_key() == "from-env"

    def test_tokenrouter_fallback(self, monkeypatch):
        monkeypatch.delenv("M3_FALLBACK_KEY", raising=False)
        monkeypatch.setenv("TOKENROUTER_API_KEY", "from-tr")
        assert _resolve_fallback_api_key() == "from-tr"

    def test_opencode_config_fallback(self, monkeypatch, tmp_path):
        """When env vars are absent, the opencode config file is the
        next fallback. We patch ``Path.exists`` to return True for our
        temp file, then verify the key comes from the config."""
        monkeypatch.delenv("M3_FALLBACK_KEY", raising=False)
        monkeypatch.delenv("TOKENROUTER_API_KEY", raising=False)
        cfg = tmp_path / "opencode.json"
        cfg.write_text(json.dumps({
            "provider": {"tokenrouter": {"options": {"apiKey": "from-config"}}}
        }))
        # The function calls Path.exists() then Path.read_text(). We
        # patch both to redirect to the temp file regardless of expanduser.
        from pathlib import Path as _Path
        real_path = _Path
        class _FakePath:
            def __init__(self, *a, **kw):
                # Pass through to real Path but capture which path was requested
                self._p = real_path(*a, **kw)
            def expanduser(self):
                return cfg
            def exists(self):
                return True
            def read_text(self, *a, **kw):
                return cfg.read_text()
            def __getattr__(self, name):
                return getattr(self._p, name)
        with patch("core.router.Path", _FakePath):
            assert _resolve_fallback_api_key() == "from-config"
