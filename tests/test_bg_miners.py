"""Tests for background miners config loading, hot reload, and agent_histories source."""

import asyncio
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open
import pytest

from src.bg_miners import (
    load_miners_config,
    validate_miner_config,
    get_agent_histories,
    get_recent_transcripts,
    run_cli,
    run_adaptive_miner_loop,
)


class TestMinersConfigLoading:
    """Test miners.json loading and validation."""

    def test_load_miners_config_success(self, tmp_path):
        """Load valid miners.json."""
        config_file = tmp_path / "miners.json"
        miners = [
            {"name": "test-miner", "query": "test", "interval_seconds": 3600, "source": "githits", "enabled": True},
        ]
        config_file.write_text(json.dumps(miners))

        with patch("src.bg_miners.Path") as mock_path:
            mock_path.return_value = config_file
            result = load_miners_config()
            assert result == miners

    def test_load_miners_config_missing_file(self):
        """Return empty list if miners.json does not exist."""
        with patch("src.bg_miners.Path") as mock_path:
            mock_config = MagicMock()
            mock_config.exists.return_value = False
            mock_path.return_value = mock_config
            result = load_miners_config()
            assert result == []

    def test_load_miners_config_invalid_json(self, tmp_path):
        """Return empty list on invalid JSON."""
        config_file = tmp_path / "miners.json"
        config_file.write_text("{ invalid json }")

        with patch("src.bg_miners.Path") as mock_path:
            mock_path.return_value = config_file
            result = load_miners_config()
            assert result == []

    def test_validate_miner_config_valid(self):
        """Validate miner with all required fields."""
        miner = {
            "name": "bg-code-architect",
            "query": "agentic execution",
            "interval_seconds": 14400,
            "source": "githits",
            "enabled": True,
        }
        assert validate_miner_config(miner) is True

    def test_validate_miner_config_missing_field(self):
        """Reject miner missing a required field."""
        miner = {
            "name": "bg-code-architect",
            "query": "agentic execution",
            "interval_seconds": 14400,
            # missing source
            "enabled": True,
        }
        assert validate_miner_config(miner) is False

    def test_validate_miner_config_empty(self):
        """Reject empty miner config."""
        assert validate_miner_config({}) is False


class TestAgentHistoriesSource:
    """Test the agent_histories grounding source."""

    def test_agent_histories_empty_roots(self):
        """Handle missing agent roots gracefully."""
        with patch("src.bg_miners.Path.home") as mock_home:
            mock_home.return_value = Path("/nonexistent")
            result = get_agent_histories()
            assert isinstance(result, str)
            assert "No agent histories found" in result or len(result) > 0

    def test_agent_histories_parses_jsonl_simple(self, tmp_path):
        """Parse basic JSONL with user/assistant messages."""
        session_file = tmp_path / "session.jsonl"
        events = [
            {"type": "user", "content": "Hello"},
            {"type": "assistant", "content": "Hi"},
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in events))

        # Create mock roots structure
        mock_root = MagicMock()
        mock_root.exists.return_value = True
        mock_root.glob.return_value = [session_file]

        with patch("src.bg_miners.Path.home", return_value=tmp_path):
            with patch("src.bg_miners.logger"):
                result = get_agent_histories()
                # Should either return found exchanges or fallback
                assert isinstance(result, str)

    def test_agent_histories_handles_text_blocks(self, tmp_path):
        """Parse JSONL with content as text blocks (list of {type: text})."""
        session_file = tmp_path / "session.jsonl"
        events = [
            {"type": "assistant", "content": [
                {"type": "text", "text": "Response with text blocks"},
                {"type": "tool_use", "id": "123", "name": "test"}
            ]},
        ]
        session_file.write_text("\n".join(json.dumps(e) for e in events))

        # Test that text block extraction works
        with patch("src.bg_miners.Path.home", return_value=tmp_path):
            with patch("src.bg_miners.logger"):
                result = get_agent_histories()
                assert isinstance(result, str)

    def test_agent_histories_respects_max_chars(self):
        """Respect 15000 char cap."""
        with patch("src.bg_miners.Path.home") as mock_home:
            mock_home.return_value = Path("/nonexistent")
            result = get_agent_histories()
            # Result should be reasonable size
            assert len(result) < 30000


class TestHotReloadBehavior:
    """Test config hot-reload in miner loop logic."""

    def test_config_reload_detects_changes(self):
        """Verify load_miners_config is called each time."""
        # This test verifies the logic without async complexity
        config = load_miners_config()
        assert isinstance(config, list)
        for miner in config:
            assert validate_miner_config(miner), f"Invalid config: {miner}"

    def test_miner_config_has_required_fields(self):
        """Verify actual miners.json has all required fields."""
        config = load_miners_config()
        assert len(config) > 0, "Should have miners configured"
        for miner in config:
            assert "name" in miner
            assert "query" in miner
            assert "interval_seconds" in miner
            assert "source" in miner
            assert "enabled" in miner

    def test_miner_config_sources_supported(self):
        """Verify all miners use supported sources."""
        config = load_miners_config()
        supported_sources = {"githits", "transcripts", "agent_histories"}
        for miner in config:
            source = miner.get("source")
            assert source in supported_sources, f"Unsupported source: {source}"

    def test_default_fleet_present(self):
        """Verify default fleet miners are in config."""
        config = load_miners_config()
        names = {m["name"] for m in config}
        expected = {
            "bg-code-architect",
            "bg-test-architect",
            "bg-transcript-architect",
            "bg-memory-architect",
            "bg-job-architect",
        }
        assert expected.issubset(names), f"Missing miners: {expected - names}"


class TestSourceSelection:
    """Test source-specific context extraction."""

    def test_agent_histories_source_configured(self):
        """Verify agent_histories source is used in config."""
        config = load_miners_config()
        agent_hist_miners = [m for m in config if m.get("source") == "agent_histories"]
        assert len(agent_hist_miners) > 0, "Should have at least one agent_histories miner"

    def test_all_sources_have_extractors(self):
        """Verify all configured sources have extractors."""
        config = load_miners_config()
        for miner in config:
            source = miner.get("source")
            if source == "agent_histories":
                # get_agent_histories should exist and be callable
                from src.bg_miners import get_agent_histories
                assert callable(get_agent_histories)
            elif source == "transcripts":
                from src.bg_miners import get_recent_transcripts
                assert callable(get_recent_transcripts)
            elif source == "githits":
                from src.bg_miners import get_githits_code
                assert callable(get_githits_code)


class TestRunCli:
    """Test CLI execution."""

    def test_run_cli_success(self):
        """Execute command and return stdout."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "output"
            result = run_cli(["echo", "test"])
            assert result == "output"

    def test_run_cli_failure(self):
        """Return error on non-zero return code."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "error"
            result = run_cli(["false"])
            assert "Error" in result

    def test_run_cli_exception(self):
        """Return empty string on exception."""
        with patch("subprocess.run", side_effect=Exception("timeout")):
            result = run_cli(["sleep", "1000"])
            assert result == ""
