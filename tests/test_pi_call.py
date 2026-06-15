"""Unit tests for src/pi_call.py."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure the src directory is on the import path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from pi_call import _provider_model, pi_call, BUDGET_MODELS, FRONTIER_MODELS


# ---------------------------------------------------------------------------
# _provider_model
# ---------------------------------------------------------------------------

def test_provider_model_tokenrouter_minimax():
    """'tokenrouter/MiniMax-M3' should split into ('tokenrouter', 'MiniMax-M3')."""
    assert _provider_model("tokenrouter/MiniMax-M3") == ("tokenrouter", "MiniMax-M3")


def test_provider_model_anthropic_claude():
    """'anthropic/claude-sonnet-4-6' should split into ('anthropic', 'claude-sonnet-4-6')."""
    assert _provider_model("anthropic/claude-sonnet-4-6") == ("anthropic", "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# pi_call: availability check
# ---------------------------------------------------------------------------

def test_pi_call_raises_runtime_error_when_pi_missing_and_provider_not_tokenrouter():
    """When the `pi` binary is not on PATH, pi_call must raise RuntimeError
    for any non-tokenrouter provider."""
    with patch("pi_call.subprocess.run", side_effect=FileNotFoundError("pi: command not found")):
        with pytest.raises(RuntimeError):
            pi_call("anthropic/claude-sonnet-4-6", prompt="hello")


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

def test_budget_models_is_non_empty_list():
    assert isinstance(BUDGET_MODELS, list)
    assert len(BUDGET_MODELS) > 0


def test_frontier_models_is_non_empty_list():
    assert isinstance(FRONTIER_MODELS, list)
    assert len(FRONTIER_MODELS) > 0
