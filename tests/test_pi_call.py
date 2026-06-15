"""Unit tests for src.pi_call."""

import pytest
from unittest.mock import patch

from src.pi_call import _provider_model, pi_call, BUDGET_MODELS, FRONTIER_MODELS


# ---------------------------------------------------------------------------
# _provider_model
# ---------------------------------------------------------------------------

def test_provider_model_tokenrouter():
    """tokenrouter prefix splits into ('tokenrouter', model_name)."""
    assert _provider_model("tokenrouter/MiniMax-M3") == ("tokenrouter", "MiniMax-M3")


def test_provider_model_anthropic():
    """anthropic prefix splits into ('anthropic', model_name)."""
    assert _provider_model("anthropic/claude-sonnet-4-6") == ("anthropic", "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# Model list constants
# ---------------------------------------------------------------------------

def test_budget_models_is_non_empty_list():
    assert isinstance(BUDGET_MODELS, list)
    assert len(BUDGET_MODELS) > 0


def test_frontier_models_is_non_empty_list():
    assert isinstance(FRONTIER_MODELS, list)
    assert len(FRONTIER_MODELS) > 0


# ---------------------------------------------------------------------------
# pi_call error handling
# ---------------------------------------------------------------------------

def test_pi_call_raises_runtime_error_when_pi_unavailable():
    """pi_call must raise RuntimeError when the pi CLI is missing and
    the provider is something other than tokenrouter (which has its own
    fallback path)."""
    with patch(
        "src.pi_call.subprocess.run",
        side_effect=FileNotFoundError("pi: command not found"),
    ):
        with pytest.raises(RuntimeError):
            pi_call("anthropic/claude-sonnet-4-6", "Hello, world")
