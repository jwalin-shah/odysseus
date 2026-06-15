"""Unit tests for src/pi_call.py."""

import os
import sys
from unittest.mock import patch

import pytest

# Ensure src/ is on the import path so we can import pi_call regardless of
# how the test runner is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pi_call import (  # noqa: E402  (path tweaked above)
    BUDGET_MODELS,
    FRONTIER_MODELS,
    _provider_model,
    pi_call,
)


# ---------------------------------------------------------------------------
# _provider_model
# ---------------------------------------------------------------------------

class TestProviderModel:
    def test_tokenrouter_minimax(self):
        provider, model = _provider_model("tokenrouter/MiniMax-M3")
        assert provider == "tokenrouter"
        assert model == "MiniMax-M3"

    def test_anthropic_claude_sonnet(self):
        provider, model = _provider_model("anthropic/claude-sonnet-4-6")
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# pi_call — failure when the `pi` CLI is unavailable
# ---------------------------------------------------------------------------

class TestPiCall:
    def test_raises_runtime_error_when_pi_unavailable_non_tokenrouter(self):
        """
        When `pi` is not on PATH and the provider is something other than
        'tokenrouter', pi_call must surface a RuntimeError rather than
        silently returning or raising a low-level subprocess error.
        """
        # Simulate `pi` not being installed / not on PATH.
        with patch(
            "pi_call.subprocess.run",
            side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'pi'"),
        ):
            with pytest.raises(RuntimeError):
                pi_call("hello world", "anthropic/claude-sonnet-4-6")

    def test_runtime_error_message_mentions_pi(self):
        """The raised RuntimeError should give the user a useful hint."""
        with patch(
            "pi_call.subprocess.run",
            side_effect=FileNotFoundError("pi: command not found"),
        ):
            with pytest.raises(RuntimeError) as excinfo:
                pi_call("hello world", "anthropic/claude-sonnet-4-6")

        assert "pi" in str(excinfo.value).lower()


# ---------------------------------------------------------------------------
# Model list constants
# ---------------------------------------------------------------------------

class TestModelLists:
    def test_budget_models_is_non_empty_list(self):
        assert isinstance(BUDGET_MODELS, list)
        assert len(BUDGET_MODELS) > 0
        # Every entry should be a non-empty string.
        for entry in BUDGET_MODELS:
            assert isinstance(entry, str)
            assert entry.strip() != ""

    def test_frontier_models_is_non_empty_list(self):
        assert isinstance(FRONTIER_MODELS, list)
        assert len(FRONTIER_MODELS) > 0
        for entry in FRONTIER_MODELS:
            assert isinstance(entry, str)
            assert entry.strip() != ""

    def test_budget_and_frontier_do_not_overlap_completely(self):
        """
        Sanity check: the two lists shouldn't be identical, otherwise the
        distinction between them is meaningless.
        """
        assert set(BUDGET_MODELS) != set(FRONTIER_MODELS)
