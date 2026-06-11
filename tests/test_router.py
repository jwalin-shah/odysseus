"""Tests for core.router — task classification, quota reading, CLI detection, dispatch.

Pure-unit tests: no real subprocess calls, no real LLM calls, no filesystem
access beyond mocked reads.
"""

import asyncio
import json
import subprocess
import time
import types
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest

from core.router import (
    TaskRouter,
    _CLI_PRIORITY,
    _CODE_TIMEOUT,
    _estimate_tokens,
    _infer_provider_from_model,
    QUOTA_LIVE_PATH,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def router():
    """Fresh TaskRouter for each test — no cached quota data."""
    return TaskRouter()


SAMPLE_QUOTA = {
    "timestamp": "2026-06-10 17:07:06 PDT",
    "unix": time.time(),  # current time → not stale
    "providers": {
        "ca": {"status": "success", "source": "tmux/ca"},
        "cb": {"status": "success", "source": "tmux/cb"},
        "gemini": {"status": "success", "source": "tmux/gemini"},
        "pioneer": {"status": "UP", "source": "http/pioneer"},
        "codex": {"status": "ok", "weekly_pct_remaining": "10", "source": "tmux/codex"},
        "agy": {"status": "success", "source": "tmux/agy"},
    },
}


# ---------------------------------------------------------------------------
# Task classification
# ---------------------------------------------------------------------------


class TestClassifyTask:
    """Verify the heuristic classifier for code / research / chat."""

    def test_explicit_hint_code(self, router):
        assert router.classify_task("anything", hint="code") == "code"

    def test_explicit_hint_research(self, router):
        assert router.classify_task("anything", hint="research") == "research"

    def test_explicit_hint_chat(self, router):
        assert router.classify_task("anything", hint="chat") == "chat"

    def test_auto_returns_valid_type(self, router):
        result = router.classify_task("hello world", hint="auto")
        assert result in ("code", "research", "chat")

    # -- Code patterns --

    def test_code_file_extension(self, router):
        assert router.classify_task("fix the bug in utils.py") == "code"

    def test_code_function_def(self, router):
        assert router.classify_task("def process_data(): needs refactoring") == "code"

    def test_code_write_keyword(self, router):
        assert router.classify_task("write a Python function to parse JSON files") == "code"

    def test_code_implement_keyword(self, router):
        assert router.classify_task("implement the retry logic for API calls") == "code"

    def test_code_code_fence(self, router):
        assert router.classify_task("fix this:\n```python\nprint('hello')\n```") == "code"

    def test_code_file_path(self, router):
        assert router.classify_task("refactor /src/main.py to use async") == "code"

    def test_code_debug(self, router):
        assert router.classify_task("debug the crash in the auth module handler") == "code"

    # -- Research patterns --

    def test_research_what_is(self, router):
        assert router.classify_task("what is the difference between REST and GraphQL") == "research"

    def test_research_how_does(self, router):
        assert router.classify_task("how does the Python garbage collector work in detail") == "research"

    def test_research_compare(self, router):
        assert router.classify_task("compare React and Vue for a large enterprise project") == "research"

    def test_research_explain(self, router):
        assert router.classify_task("explain the CAP theorem and its practical implications") == "research"

    def test_research_url(self, router):
        assert router.classify_task("summarize https://example.com/article about new features") == "research"

    def test_research_find(self, router):
        assert router.classify_task("find the best practices for database indexing strategies") == "research"

    # -- Chat patterns --

    def test_chat_greeting(self, router):
        assert router.classify_task("hello!") == "chat"

    def test_chat_short_thanks(self, router):
        assert router.classify_task("thanks") == "chat"

    def test_chat_good_morning(self, router):
        assert router.classify_task("good morning") == "chat"

    def test_chat_short_ambiguous(self, router):
        assert router.classify_task("ok") == "chat"

    def test_chat_whats_up(self, router):
        assert router.classify_task("what's up?") == "chat"

    # -- Edge / ambiguous --

    def test_ambiguous_defaults_chat(self, router):
        """Truly ambiguous input defaults to chat (cheapest)."""
        assert router.classify_task("I need help") == "chat"

    def test_empty_auto_hint_treated_as_auto(self, router):
        result = router.classify_task("hello", hint="")
        assert result in ("code", "research", "chat")

    def test_invalid_hint_treated_as_auto(self, router):
        result = router.classify_task("hello", hint="banana")
        assert result in ("code", "research", "chat")


# ---------------------------------------------------------------------------
# Quota reading
# ---------------------------------------------------------------------------


class TestGetQuotaStatus:
    """Verify quota file reading + caching behaviour."""

    def test_reads_quota_file(self, router):
        quota_json = json.dumps(SAMPLE_QUOTA)
        with patch.object(Path, "read_text", return_value=quota_json):
            result = router.get_quota_status()
        assert "providers" in result
        assert result["providers"]["ca"]["status"] == "success"

    def test_caches_result(self, router):
        quota_json = json.dumps(SAMPLE_QUOTA)
        with patch.object(Path, "read_text", return_value=quota_json) as mock_read:
            router.get_quota_status()
            router.get_quota_status()  # second call should use cache
        assert mock_read.call_count == 1

    def test_cache_expires(self, router):
        quota_json = json.dumps(SAMPLE_QUOTA)
        with patch.object(Path, "read_text", return_value=quota_json) as mock_read:
            router.get_quota_status()
            # Expire the cache
            router._quota_cache_time = 0
            router.get_quota_status()
        assert mock_read.call_count == 2

    def test_missing_file_returns_safe_fallback(self, router):
        with patch.object(Path, "read_text", side_effect=FileNotFoundError("nope")):
            result = router.get_quota_status()
        assert result["providers"] == {}

    def test_corrupt_json_returns_safe_fallback(self, router):
        with patch.object(Path, "read_text", return_value="not json{{{"):
            result = router.get_quota_status()
        assert result["providers"] == {}

    def test_stale_data_logs_warning(self, router, caplog):
        stale_quota = {**SAMPLE_QUOTA, "unix": time.time() - 1200}  # 20 min old
        with patch.object(Path, "read_text", return_value=json.dumps(stale_quota)):
            import logging
            with caplog.at_level(logging.WARNING):
                router.get_quota_status()
        assert any("stale" in r.message.lower() for r in caplog.records)


# ---------------------------------------------------------------------------
# CLI binary detection
# ---------------------------------------------------------------------------


class TestGetBestCodeCLI:
    """Verify account priority selection based on config dirs + quota status.

    `ca`/`cb` are zsh functions, not binaries — selection checks the account's
    CLAUDE_CONFIG_DIR instead of shutil.which (which can never see them)."""

    def test_picks_first_available(self, router):
        quota_json = json.dumps(SAMPLE_QUOTA)
        with patch.object(Path, "read_text", return_value=quota_json):
            with patch.object(Path, "is_dir", return_value=True):
                account, provider = router.get_best_code_cli()
        assert account == "ca"
        assert provider == "ca"

    def test_skips_missing_config_dir(self, router):
        quota_json = json.dumps(SAMPLE_QUOTA)
        with patch.object(Path, "read_text", return_value=quota_json):
            # .claude-a missing, .claude-b present
            with patch.object(
                Path, "is_dir", lambda self: str(self).endswith(".claude-b")
            ):
                account, provider = router.get_best_code_cli()
        assert account == "cb"
        assert provider == "cb"

    def test_skips_exhausted_provider(self, router):
        exhausted = {**SAMPLE_QUOTA}
        exhausted["providers"] = {
            **exhausted["providers"],
            "ca": {"status": "exhausted"},
        }
        with patch.object(Path, "read_text", return_value=json.dumps(exhausted)):
            with patch.object(Path, "is_dir", return_value=True):
                account, provider = router.get_best_code_cli()
        assert account == "cb"
        assert provider == "cb"

    def test_fallback_when_nothing_found(self, router):
        with patch.object(Path, "read_text", return_value=json.dumps(SAMPLE_QUOTA)):
            with patch.object(Path, "is_dir", return_value=False):
                account, provider = router.get_best_code_cli()
        assert account == "default"
        assert provider == "claude"

    def test_build_code_command_selects_account_via_config_dir(self, router):
        with patch("shutil.which", return_value="/opt/homebrew/bin/claude"):
            argv, env = router.build_code_command("cb", "do the thing")
        assert argv[0] == "/opt/homebrew/bin/claude"
        assert argv[-1] == "do the thing"
        assert env["CLAUDE_CONFIG_DIR"].endswith(".claude-b")

    def test_build_code_command_default_account_uses_default_profile(self, router):
        with patch("shutil.which", return_value="/opt/homebrew/bin/claude"):
            argv, env = router.build_code_command("default", "task")
        assert "CLAUDE_CONFIG_DIR" not in env


# ---------------------------------------------------------------------------
# Dispatch: code via subprocess
# ---------------------------------------------------------------------------


class TestRouteCode:
    """Test code dispatch via subprocess."""

    def test_success(self, router):
        with patch.object(Path, "read_text", return_value=json.dumps(SAMPLE_QUOTA)), \
             patch.object(Path, "is_dir", return_value=True):
            with patch("shutil.which", return_value="/usr/bin/claude"):
                mock_result = subprocess.CompletedProcess(
                    args=["ca", "--print", "-p", "test"],
                    returncode=0,
                    stdout="Generated code output",
                    stderr="",
                )
                with patch("subprocess.run", return_value=mock_result):
                    result = asyncio.run(
                        router.route_code("write a hello world")
                    )
        assert result["response"] == "Generated code output"
        assert result["provider"] == "ca"
        assert result["tokens"] > 0
        assert "error" not in result

    def test_timeout(self, router):
        with patch.object(Path, "read_text", return_value=json.dumps(SAMPLE_QUOTA)), \
             patch.object(Path, "is_dir", return_value=True):
            with patch("shutil.which", return_value="/usr/bin/claude"):
                with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("ca", 300)):
                    result = asyncio.run(
                        router.route_code("complex task")
                    )
        assert result["error"] is True
        assert "timed out" in result["response"].lower()

    def test_binary_not_found(self, router):
        with patch.object(Path, "read_text", return_value=json.dumps(SAMPLE_QUOTA)), \
             patch.object(Path, "is_dir", return_value=True):
            with patch("shutil.which", return_value="/usr/bin/claude"):
                with patch("subprocess.run", side_effect=FileNotFoundError("ca")):
                    result = asyncio.run(
                        router.route_code("some task")
                    )
        assert result["error"] is True
        assert "not found" in result["response"].lower()

    def test_nonzero_exit_empty_stdout_returns_stderr_as_error(self, router):
        """Non-zero exit with empty stdout should return stderr text with error:True."""
        with patch.object(Path, "read_text", return_value=json.dumps(SAMPLE_QUOTA)), \
             patch.object(Path, "is_dir", return_value=True):
            with patch("shutil.which", return_value="/usr/bin/claude"):
                mock_result = subprocess.CompletedProcess(
                    args=["ca", "--print", "-p", "test"],
                    returncode=1,
                    stdout="",
                    stderr="Some CLI error occurred",
                )
                with patch("subprocess.run", return_value=mock_result):
                    result = asyncio.run(
                        router.route_code("some task")
                    )
        assert result["error"] is True
        assert "Some CLI error occurred" in result["response"]


# ---------------------------------------------------------------------------
# Dispatch: research via LLM
# ---------------------------------------------------------------------------


class TestRouteResearch:
    """Test research dispatch via llm_call_async."""

    def test_success(self, router):
        mock_resolve = MagicMock(return_value=(
            "http://localhost:8000/v1/chat/completions",
            "gemini-3-flash",
            {"Authorization": "Bearer test"},
        ))
        mock_llm = AsyncMock(return_value="Research results here")

        with patch("core.router.TaskRouter.route_research.__module__", "core.router"):
            with patch("src.endpoint_resolver.resolve_endpoint", mock_resolve):
                with patch("src.llm_core.llm_call_async", mock_llm):
                    result = asyncio.run(
                        router.route_research("what is quantum computing")
                    )
        assert result["response"] == "Research results here"
        assert result["model_used"] == "gemini-3-flash"
        assert result["provider"] == "gemini"
        assert "error" not in result

    def test_no_endpoint_configured(self, router):
        mock_resolve = MagicMock(return_value=(None, None, None))

        with patch("src.endpoint_resolver.resolve_endpoint", mock_resolve):
            result = asyncio.run(
                router.route_research("find info")
            )
        assert result["error"] is True
        assert "no research endpoint" in result["response"].lower()


# ---------------------------------------------------------------------------
# Dispatch: chat via cheapest model
# ---------------------------------------------------------------------------


class TestRouteChat:
    """Test chat dispatch via llm_call_async."""

    def test_success(self, router):
        mock_resolve = MagicMock(return_value=(
            "http://localhost:8000/v1/chat/completions",
            "minimax-m3",
            {"Authorization": "Bearer test"},
        ))
        mock_llm = AsyncMock(return_value="Hello! How can I help?")

        with patch("src.endpoint_resolver.resolve_endpoint", mock_resolve):
            with patch("src.llm_core.llm_call_async", mock_llm):
                result = asyncio.run(
                    router.route_chat("hello")
                )
        assert result["response"] == "Hello! How can I help?"
        assert result["model_used"] == "minimax-m3"
        assert result["provider"] == "minimax"

    def test_no_endpoint_configured(self, router):
        mock_resolve = MagicMock(return_value=(None, None, None))

        with patch("src.endpoint_resolver.resolve_endpoint", mock_resolve):
            result = asyncio.run(
                router.route_chat("hi")
            )
        assert result["error"] is True


# ---------------------------------------------------------------------------
# Main route() entry point
# ---------------------------------------------------------------------------


class TestRoute:
    """Test the main route() orchestrator."""

    def test_empty_task(self, router):
        result = asyncio.run(
            router.route("")
        )
        assert result["error"] is True
        assert result["classification"] == "error"

    def test_auto_classification_and_dispatch(self, router):
        mock_resolve = MagicMock(return_value=(
            "http://localhost:8000/v1/chat/completions",
            "test-model",
            {},
        ))
        mock_llm = AsyncMock(return_value="response")

        with patch("src.endpoint_resolver.resolve_endpoint", mock_resolve):
            with patch("src.llm_core.llm_call_async", mock_llm):
                result = asyncio.run(
                    router.route("hello!", task_type="auto")
                )
        assert result["classification"] == "chat"
        assert "response" in result

    def test_explicit_type_skips_classification(self, router):
        mock_resolve = MagicMock(return_value=(
            "http://localhost:8000/v1/chat/completions",
            "gemini-3-flash",
            {},
        ))
        mock_llm = AsyncMock(return_value="research result")

        with patch("src.endpoint_resolver.resolve_endpoint", mock_resolve):
            with patch("src.llm_core.llm_call_async", mock_llm):
                result = asyncio.run(
                    router.route("hello", task_type="research")
                )
        assert result["classification"] == "research"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestHelpers:
    def test_estimate_tokens_empty(self):
        assert _estimate_tokens("") == 0

    def test_estimate_tokens_short(self):
        assert _estimate_tokens("hello") >= 1

    def test_estimate_tokens_proportional(self):
        short = _estimate_tokens("hello world")
        long = _estimate_tokens("hello world " * 100)
        assert long > short

    def test_infer_provider_gemini(self):
        assert _infer_provider_from_model("gemini-3-flash") == "gemini"

    def test_infer_provider_claude(self):
        assert _infer_provider_from_model("claude-sonnet-4") == "anthropic"

    def test_infer_provider_openai(self):
        assert _infer_provider_from_model("gpt-4o") == "openai"

    def test_infer_provider_minimax(self):
        assert _infer_provider_from_model("minimax-m3") == "minimax"

    def test_infer_provider_unknown(self):
        assert _infer_provider_from_model("some-random-model") == "unknown"
