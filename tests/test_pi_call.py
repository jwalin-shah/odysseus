"""Unit tests for src/pi_call.py."""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Make the src/ directory importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pi_call import _provider_model, pi_call, BUDGET_MODELS, FRONTIER_MODELS  # noqa: E402


# ---------------------------------------------------------------------------
# _provider_model
# ---------------------------------------------------------------------------
class TestProviderModel:
    def test_tokenrouter_minimax(self):
        provider, model = _provider_model("tokenrouter/MiniMax-M3")
        assert provider == "tokenrouter"
        assert model == "MiniMax-M3"

    def test_anthropic_claude(self):
        provider, model = _provider_model("anthropic/claude-sonnet-4-6")
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# pi_call — failure when pi binary is unavailable
# ---------------------------------------------------------------------------
class TestPiCallUnavailable:
    def test_raises_runtime_error_when_pi_binary_missing(self):
        """FileNotFoundError from subprocess → RuntimeError for non-tokenrouter provider."""
        with patch("subprocess.run", side_effect=FileNotFoundError("pi: command not found")):
            with pytest.raises(RuntimeError):
                pi_call("anthropic/claude-sonnet-4-6", prompt="hello")

    def test_raises_runtime_error_when_pi_returns_nonzero(self):
        """Non-zero exit code from subprocess → RuntimeError for non-tokenrouter provider."""
        fake = MagicMock()
        fake.returncode = 127
        fake.stderr = "pi: command not found"
        fake.stdout = ""

        with patch("subprocess.run", return_value=fake):
            with pytest.raises(RuntimeError):
                pi_call("anthropic/claude-sonnet-4-6", prompt="hello")


# ---------------------------------------------------------------------------
# Model list constants
# ---------------------------------------------------------------------------
class TestModelLists:
    def test_budget_models_is_non_empty_list(self):
        assert isinstance(BUDGET_MODELS, list)
        assert len(BUDGET_MODELS) > 0

    def test_frontier_models_is_non_empty_list(self):
        assert isinstance(FRONTIER_MODELS, list)
        assert len(FRONTIER_MODELS) > 0
