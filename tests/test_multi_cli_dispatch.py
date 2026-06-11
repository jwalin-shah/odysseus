# tests/test_multi_cli_dispatch.py
"""Tests for Feature 1 — multi-CLI adapter table dispatch.

Covers:
  - Adapter table structure and completeness
  - select_adapter() fallback order: claude-ca → claude-cb → codex → gemini
  - Quota exhaustion skipping (claude status, codex weekly_pct_remaining, gemini pct_used)
  - Binary not found → skip to next adapter
  - All adapters unavailable → in-band error from route_code
  - parse_output functions: claude JSON parsing with session_id, codex plain text, gemini plain text
  - build_adapter_command sets CLAUDE_CONFIG_DIR for claude adapters only
  - codex exhaustion at weekly_pct_remaining <= 5
  - gemini exhaustion at pct_used >= 100

All tests mock CLI execution — no real binaries are invoked.
"""

import asyncio
import json
import subprocess
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from core.router import (
    TaskRouter,
    _CLI_ADAPTERS,
    _claude_is_exhausted,
    _codex_is_exhausted,
    _gemini_is_exhausted,
    _claude_parse_output,
    _codex_parse_output,
    _gemini_parse_output,
    QUOTA_LIVE_PATH,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _quota_with(overrides: dict) -> str:
    """Return quota JSON with provider overrides."""
    base = {
        "timestamp": "2026-06-11",
        "unix": time.time(),
        "providers": {
            "ca": {"status": "success"},
            "cb": {"status": "success"},
            "codex": {"status": "ok", "weekly_pct_remaining": "50"},
            "gemini": {
                "status": "success",
                "quotas": {"models": {"gemini-flash": {"pct_used": "10"}}},
            },
        },
    }
    base["providers"].update(overrides)
    return json.dumps(base)


@pytest.fixture
def router():
    return TaskRouter()


# ---------------------------------------------------------------------------
# Adapter table structure
# ---------------------------------------------------------------------------


class TestAdapterTable:
    """_CLI_ADAPTERS is well-formed and covers the required backends."""

    def test_table_has_four_entries(self):
        assert len(_CLI_ADAPTERS) == 4

    def test_first_two_are_claude(self):
        assert _CLI_ADAPTERS[0]["name"] == "claude-ca"
        assert _CLI_ADAPTERS[1]["name"] == "claude-cb"

    def test_codex_is_third(self):
        assert _CLI_ADAPTERS[2]["name"] == "codex"

    def test_gemini_is_fourth(self):
        assert _CLI_ADAPTERS[3]["name"] == "gemini"

    def test_all_have_required_keys(self):
        required = {"name", "provider_key", "binary", "build_argv", "is_exhausted", "parse_output", "supports_resume"}
        for adapter in _CLI_ADAPTERS:
            assert required.issubset(adapter.keys()), f"Adapter {adapter['name']} missing keys"

    def test_claude_adapters_support_resume(self):
        for adapter in _CLI_ADAPTERS:
            if "claude" in adapter["name"]:
                assert adapter["supports_resume"] is True

    def test_codex_gemini_do_not_support_resume(self):
        for adapter in _CLI_ADAPTERS:
            if adapter["name"] in ("codex", "gemini"):
                assert adapter["supports_resume"] is False

    def test_claude_adapters_have_config_dir(self):
        for adapter in _CLI_ADAPTERS:
            if "claude" in adapter["name"]:
                assert adapter.get("config_dir") is not None

    def test_codex_gemini_no_config_dir(self):
        for adapter in _CLI_ADAPTERS:
            if adapter["name"] in ("codex", "gemini"):
                assert adapter.get("config_dir") is None


# ---------------------------------------------------------------------------
# Exhaustion predicates
# ---------------------------------------------------------------------------


class TestExhaustionPredicates:
    def test_claude_success_not_exhausted(self):
        assert not _claude_is_exhausted({"status": "success"})

    def test_claude_exhausted_status(self):
        assert _claude_is_exhausted({"status": "exhausted"})

    def test_claude_rate_limited(self):
        assert _claude_is_exhausted({"status": "rate_limited"})

    def test_codex_plenty_remaining(self):
        assert not _codex_is_exhausted({"weekly_pct_remaining": "50"})

    def test_codex_exactly_5_is_exhausted(self):
        assert _codex_is_exhausted({"weekly_pct_remaining": "5"})

    def test_codex_4_is_exhausted(self):
        assert _codex_is_exhausted({"weekly_pct_remaining": "4"})

    def test_codex_0_is_exhausted(self):
        assert _codex_is_exhausted({"weekly_pct_remaining": "0"})

    def test_codex_6_not_exhausted(self):
        assert not _codex_is_exhausted({"weekly_pct_remaining": "6"})

    def test_codex_10_not_exhausted(self):
        assert not _codex_is_exhausted({"weekly_pct_remaining": "10"})

    def test_codex_missing_pct_defaults_not_exhausted(self):
        assert not _codex_is_exhausted({})

    def test_codex_exhausted_status_override(self):
        assert _codex_is_exhausted({"status": "exhausted", "weekly_pct_remaining": "50"})

    def test_gemini_success_not_exhausted(self):
        assert not _gemini_is_exhausted({
            "status": "success",
            "quotas": {"models": {"flash": {"pct_used": "50"}}},
        })

    def test_gemini_pct_used_100(self):
        assert _gemini_is_exhausted({
            "status": "success",
            "quotas": {"models": {"flash": {"pct_used": "100"}}},
        })

    def test_gemini_exhausted_status(self):
        assert _gemini_is_exhausted({"status": "exhausted"})

    def test_gemini_no_quotas_not_exhausted(self):
        assert not _gemini_is_exhausted({"status": "success"})


# ---------------------------------------------------------------------------
# select_adapter — fallback order
# ---------------------------------------------------------------------------


class TestSelectAdapter:
    """select_adapter walks the table and picks the first usable adapter."""

    def _make_is_dir(self, present: list):
        """Return a Path.is_dir side-effect: True only for paths ending with one of `present`."""
        def is_dir(self_path):
            return any(str(self_path).endswith(p) for p in present)
        return is_dir

    def test_selects_claude_ca_first(self, router):
        with patch.object(Path, "read_text", return_value=_quota_with({})), \
             patch.object(Path, "is_dir", return_value=True), \
             patch("shutil.which", return_value="/usr/bin/claude"):
            adapter = router.select_adapter()
        assert adapter is not None
        assert adapter["name"] == "claude-ca"

    def test_skips_ca_when_missing_config_dir(self, router):
        """If .claude-a is missing, should pick claude-cb."""
        with patch.object(Path, "read_text", return_value=_quota_with({})), \
             patch.object(Path, "is_dir", self._make_is_dir([".claude-b"])), \
             patch("shutil.which", return_value="/usr/bin/claude"):
            adapter = router.select_adapter()
        assert adapter is not None
        assert adapter["name"] == "claude-cb"

    def test_skips_ca_when_exhausted(self, router):
        quota = _quota_with({"ca": {"status": "exhausted"}})
        with patch.object(Path, "read_text", return_value=quota), \
             patch.object(Path, "is_dir", return_value=True), \
             patch("shutil.which", return_value="/usr/bin/claude"):
            adapter = router.select_adapter()
        assert adapter is not None
        assert adapter["name"] == "claude-cb"

    def test_skips_both_claude_falls_back_to_codex(self, router):
        quota = _quota_with({
            "ca": {"status": "exhausted"},
            "cb": {"status": "exhausted"},
            "codex": {"status": "ok", "weekly_pct_remaining": "50"},
        })

        def which_side_effect(binary):
            if binary == "codex":
                return "/opt/homebrew/bin/codex"
            return None  # claude binary not found

        with patch.object(Path, "read_text", return_value=quota), \
             patch.object(Path, "is_dir", return_value=False), \
             patch("shutil.which", side_effect=which_side_effect):
            adapter = router.select_adapter()
        assert adapter is not None
        assert adapter["name"] == "codex"

    def test_skips_codex_exhausted_falls_back_to_gemini(self, router):
        quota = _quota_with({
            "ca": {"status": "exhausted"},
            "cb": {"status": "exhausted"},
            "codex": {"status": "ok", "weekly_pct_remaining": "3"},  # <=5 = exhausted
            "gemini": {
                "status": "success",
                "quotas": {"models": {"flash": {"pct_used": "10"}}},
            },
        })

        def which_side_effect(binary):
            if binary == "gemini":
                return "/opt/homebrew/bin/gemini"
            return None

        with patch.object(Path, "read_text", return_value=quota), \
             patch.object(Path, "is_dir", return_value=False), \
             patch("shutil.which", side_effect=which_side_effect):
            adapter = router.select_adapter()
        assert adapter is not None
        assert adapter["name"] == "gemini"

    def test_all_exhausted_returns_none(self, router):
        quota = _quota_with({
            "ca": {"status": "exhausted"},
            "cb": {"status": "exhausted"},
            "codex": {"status": "ok", "weekly_pct_remaining": "0"},
            "gemini": {"status": "exhausted"},
        })
        with patch.object(Path, "read_text", return_value=quota), \
             patch.object(Path, "is_dir", return_value=False), \
             patch("shutil.which", return_value=None):
            adapter = router.select_adapter()
        assert adapter is None

    def test_all_unavailable_returns_none(self, router):
        """Even with good quota, no binary → None."""
        with patch.object(Path, "read_text", return_value=_quota_with({})), \
             patch.object(Path, "is_dir", return_value=False), \
             patch("shutil.which", return_value=None):
            adapter = router.select_adapter()
        assert adapter is None


# ---------------------------------------------------------------------------
# route_code uses adapter table
# ---------------------------------------------------------------------------


class TestRouteCodeAdapterIntegration:
    """route_code picks the right adapter and returns provider name from table."""

    def test_route_code_uses_claude_ca(self, router):
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout=json.dumps({"type": "result", "result": "done", "session_id": "sess-abc"}),
            stderr="",
        )
        with patch.object(Path, "read_text", return_value=_quota_with({})), \
             patch.object(Path, "is_dir", return_value=True), \
             patch("shutil.which", return_value="/usr/bin/claude"), \
             patch("subprocess.run", return_value=mock_result):
            result = asyncio.run(router.route_code("write a hello world"))
        assert result["provider"] == "claude-ca"
        assert result["session_id"] == "sess-abc"
        assert result["response"] == "done"
        assert "error" not in result

    def test_route_code_falls_back_to_codex(self, router):
        quota = _quota_with({
            "ca": {"status": "exhausted"},
            "cb": {"status": "exhausted"},
            "codex": {"status": "ok", "weekly_pct_remaining": "50"},
        })
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="codex output here",
            stderr="",
        )

        def which_side_effect(binary):
            if binary == "codex":
                return "/opt/homebrew/bin/codex"
            return None

        with patch.object(Path, "read_text", return_value=quota), \
             patch.object(Path, "is_dir", return_value=False), \
             patch("shutil.which", side_effect=which_side_effect), \
             patch("subprocess.run", return_value=mock_result):
            result = asyncio.run(router.route_code("write a script"))
        assert result["provider"] == "codex"
        assert result["response"] == "codex output here"
        assert "session_id" not in result
        assert "error" not in result

    def test_route_code_falls_back_to_gemini(self, router):
        quota = _quota_with({
            "ca": {"status": "exhausted"},
            "cb": {"status": "exhausted"},
            "codex": {"status": "ok", "weekly_pct_remaining": "0"},
            "gemini": {
                "status": "success",
                "quotas": {"models": {"flash": {"pct_used": "10"}}},
            },
        })
        mock_result = subprocess.CompletedProcess(
            args=[], returncode=0,
            stdout="gemini output",
            stderr="",
        )

        def which_side_effect(binary):
            if binary == "gemini":
                return "/opt/homebrew/bin/gemini"
            return None

        with patch.object(Path, "read_text", return_value=quota), \
             patch.object(Path, "is_dir", return_value=False), \
             patch("shutil.which", side_effect=which_side_effect), \
             patch("subprocess.run", return_value=mock_result):
            result = asyncio.run(router.route_code("write a script"))
        assert result["provider"] == "gemini"
        assert result["response"] == "gemini output"
        assert "error" not in result

    def test_route_code_all_exhausted_returns_error(self, router):
        quota = _quota_with({
            "ca": {"status": "exhausted"},
            "cb": {"status": "exhausted"},
            "codex": {"status": "ok", "weekly_pct_remaining": "0"},
            "gemini": {"status": "exhausted"},
        })
        with patch.object(Path, "read_text", return_value=quota), \
             patch.object(Path, "is_dir", return_value=False), \
             patch("shutil.which", return_value=None):
            result = asyncio.run(router.route_code("write a script"))
        assert result["error"] is True
        assert "exhausted" in result["response"].lower() or "unavailable" in result["response"].lower()


# ---------------------------------------------------------------------------
# parse_output functions
# ---------------------------------------------------------------------------


class TestParseOutput:
    def test_claude_parses_json_with_session_id(self):
        payload = json.dumps({
            "type": "result",
            "subtype": "success",
            "result": "hello world",
            "session_id": "abc-123",
        })
        text, session_id = _claude_parse_output(payload, "", 0)
        assert text == "hello world"
        assert session_id == "abc-123"

    def test_claude_falls_back_on_non_json(self):
        text, session_id = _claude_parse_output("plain output", "", 0)
        assert text == "plain output"
        assert session_id is None

    def test_claude_empty_stdout_uses_stderr(self):
        text, session_id = _claude_parse_output("", "error msg", 1)
        assert text == "error msg"
        assert session_id is None

    def test_claude_json_without_session_id(self):
        payload = json.dumps({"type": "result", "result": "output only"})
        text, session_id = _claude_parse_output(payload, "", 0)
        assert text == "output only"
        assert session_id is None

    def test_codex_plain_text(self):
        text, session_id = _codex_parse_output("codex result", "", 0)
        assert text == "codex result"
        assert session_id is None

    def test_gemini_plain_text(self):
        text, session_id = _gemini_parse_output("gemini answer", "", 0)
        assert text == "gemini answer"
        assert session_id is None


# ---------------------------------------------------------------------------
# build_adapter_command
# ---------------------------------------------------------------------------


class TestBuildAdapterCommand:
    def test_claude_adapter_sets_config_dir(self, router):
        adapter = next(a for a in _CLI_ADAPTERS if a["name"] == "claude-ca")
        with patch("shutil.which", return_value="/usr/bin/claude"):
            argv, env = router.build_adapter_command(adapter, "do something")
        assert env["CLAUDE_CONFIG_DIR"].endswith(".claude-a")
        assert "/usr/bin/claude" in argv[0]
        assert "--output-format" in argv
        assert "json" in argv

    def test_codex_adapter_no_config_dir(self, router):
        adapter = next(a for a in _CLI_ADAPTERS if a["name"] == "codex")
        with patch("shutil.which", return_value="/opt/homebrew/bin/codex"):
            argv, env = router.build_adapter_command(adapter, "task")
        assert "CLAUDE_CONFIG_DIR" not in env
        assert "exec" in argv

    def test_gemini_adapter_uses_p_flag(self, router):
        adapter = next(a for a in _CLI_ADAPTERS if a["name"] == "gemini")
        with patch("shutil.which", return_value="/opt/homebrew/bin/gemini"):
            argv, env = router.build_adapter_command(adapter, "my task")
        assert "-p" in argv
        assert "my task" in argv
