"""Unit tests for src/pi_call.py."""

import os
import sys
from unittest.mock import patch

import pytest

# Make `src/pi_call.py` importable when tests are run from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pi_call import _provider_model, pi_call, BUDGET_MODELS, FRONTIER_MODELS


# ---------------------------------------------------------------------------
# _provider_model
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "model_str, expected",
    [
        # (1) tokenrouter/MiniMax-M3
        ("tokenrouter/MiniMax-M3", ("tokenrouter", "MiniMax-M3")),
        # (2) anthropic/claude-sonnet-4-6
        ("anthropic/claude-sonnet-4-6", ("anthropic", "claude-sonnet-4-6")),
    ],
)
def test_provider_model(model_str, expected):
    """`_provider_model` should split '<provider>/<model>' on the first slash
    and return a (provider, model) tuple of strings."""
    assert _provider_model(model_str) == expected


# ---------------------------------------------------------------------------
# Model registry constants
# ---------------------------------------------------------------------------

def test_budget_models_is_non_empty_list():
    """BUDGET_MODELS must be a list with at least one entry."""
    assert isinstance(BUDGET_MODELS, list)
    assert len(BUDGET_MODELS) > 0


def test_frontier_models_is_non_empty_list():
    """FRONTIER_MODELS must be a list with at least one entry."""
    assert isinstance(FRONTIER_MODELS, list)
    assert len(FRONTIER_MODELS) > 0


# ---------------------------------------------------------------------------
# pi_call error handling
# ---------------------------------------------------------------------------

def test_pi_call_raises_runtime_error_when_pi_cli_missing():
    """When the `pi` binary is not on PATH and the resolved provider is not
    `tokenrouter`, `pi_call` must surface a `RuntimeError` (with a helpful
    message) instead of letting the raw `FileNotFoundError` from
    `subprocess.run` bubble up to the caller."""
    with patch("subprocess.run", side_effect=FileNotFoundError("pi: command not found")):
        with pytest.raises(RuntimeError):
            pi_call("anthropic/claude-sonnet-4-6", prompt="Hello, world.")
