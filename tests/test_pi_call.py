"""Unit tests for src/pi_call.py."""
import sys
import pytest
from unittest.mock import patch

# Make the src/ package importable regardless of how pytest is invoked.
sys.path.insert(0, "src")

from pi_call import (  # noqa: E402
    _provider_model,
    pi_call,
    BUDGET_MODELS,
    FRONTIER_MODELS,
)


# ---------------------------------------------------------------------------
# _provider_model
# ---------------------------------------------------------------------------

class TestProviderModel:
    """The _provider_model helper splits a 'provider/model' string."""

    def test_tokenrouter(self):
        assert _provider_model("tokenrouter/MiniMax-M3") == (
            "tokenrouter",
            "MiniMax-M3",
        )

    def test_anthropic(self):
        assert _provider_model("anthropic/claude-sonnet-4-6") == (
            "anthropic",
            "claude-sonnet-4-6",
        )


# ---------------------------------------------------------------------------
# Model-list constants
# ---------------------------------------------------------------------------

def test_budget_models_is_non_empty_list():
    assert isinstance(BUDGET_MODELS, list)
    assert len(BUDGET_MODELS) > 0


def test_frontier_models_is_non_empty_list():
    assert isinstance(FRONTIER_MODELS, list)
    assert len(FRONTIER_MODELS) > 0


# ---------------------------------------------------------------------------
# pi_call when the `pi` binary is missing
# ---------------------------------------------------------------------------

class TestPiCallWhenPiUnavailable:
    """pi_call must surface a RuntimeError when `pi` cannot be exec'd and
    the requested provider is not the local 'tokenrouter' fallback."""

    @patch("pi_call.subprocess.run")
    def test_raises_runtime_error_for_non_tokenrouter_provider(self, mock_run):
        # Simulate the `pi` binary not being installed: subprocess.run
        # raises FileNotFoundError, which is what the real call would do.
        mock_run.side_effect = FileNotFoundError(
            "[Errno 2] No such file or directory: 'pi'"
        )

        with pytest.raises(RuntimeError):
            pi_call("anthropic/claude-sonnet-4-6", "Hello, world!")
