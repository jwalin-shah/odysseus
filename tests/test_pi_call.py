"""Unit tests for src/pi_call.py."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from src.pi_call import (
    BUDGET_MODELS,
    FRONTIER_MODELS,
    _provider_model,
    pi_call,
)


# ---------------------------------------------------------------------------
# _provider_model
# ---------------------------------------------------------------------------
class TestProviderModel:
    def test_tokenrouter(self):
        assert _provider_model("tokenrouter/MiniMax-M3") == ("tokenrouter", "MiniMax-M3")

    def test_anthropic(self):
        assert _provider_model("anthropic/claude-sonnet-4-6") == ("anthropic", "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# pi_call — when the local `pi` binary is missing and provider != tokenrouter
# ---------------------------------------------------------------------------
class TestPiCallMissingBinary:
    def test_raises_runtime_error_for_anthropic(self):
        # Simulate `pi` not being installed: subprocess.run raises FileNotFoundError
        with patch("src.pi_call.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError):
                pi_call("anthropic/claude-sonnet-4-6", prompt="hello")

    def test_raises_runtime_error_for_openai(self):
        with patch("src.pi_call.subprocess.run", side_effect=FileNotFoundError):
            with pytest.raises(RuntimeError):
                pi_call("openai/gpt-4o", prompt="hello")


# ---------------------------------------------------------------------------
# Model-list constants
# ---------------------------------------------------------------------------
class TestModelConstants:
    def test_budget_models_non_empty(self):
        assert isinstance(BUDGET_MODELS, list)
        assert len(BUDGET_MODELS) > 0

    def test_frontier_models_non_empty(self):
        assert isinstance(FRONTIER_MODELS, list)
        assert len(FRONTIER_MODELS) > 0
