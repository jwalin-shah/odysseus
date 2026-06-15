"""Unit tests for src/pi_call.py."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Ensure src/ is importable when running pytest from the project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pi_call import (  # noqa: E402
    _provider_model,
    pi_call,
    BUDGET_MODELS,
    FRONTIER_MODELS,
)


# ---------------------------------------------------------------------------
# _provider_model
# ---------------------------------------------------------------------------

def test_provider_model_tokenrouter():
    """_provider_model parses 'tokenrouter/MiniMax-M3' into the expected tuple."""
    assert _provider_model("tokenrouter/MiniMax-M3") == ("tokenrouter", "MiniMax-M3")


def test_provider_model_anthropic():
    """_provider_model parses 'anthropic/claude-sonnet-4-6' into the expected tuple."""
    assert _provider_model("anthropic/claude-sonnet-4-6") == ("anthropic", "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# pi_call error handling
# ---------------------------------------------------------------------------

def test_pi_call_raises_runtime_error_when_pi_unavailable_for_non_tokenrouter():
    """pi_call raises RuntimeError when the 'pi' binary is missing
    and the requested model belongs to a non-tokenrouter provider."""
    with patch("pi_call.subprocess.run") as mock_run:
        # Simulate the 'pi' binary not being installed / not on PATH
        mock_run.side_effect = FileNotFoundError(
            "[Errno 2] No such file or directory: 'pi'"
        )

        with pytest.raises(RuntimeError):
            pi_call("anthropic/claude-sonnet-4-6", "hello world")


# ---------------------------------------------------------------------------
# Model registry constants
# ---------------------------------------------------------------------------

def test_budget_models_is_non_empty_list():
    """BUDGET_MODELS is a non-empty list."""
    assert isinstance(BUDGET_MODELS, list), "BUDGET_MODELS must be a list"
    assert len(BUDGET_MODELS) > 0, "BUDGET_MODELS must not be empty"


def test_frontier_models_is_non_empty_list():
    """FRONTIER_MODELS is a non-empty list."""
    assert isinstance(FRONTIER_MODELS, list), "FRONTIER_MODELS must be a list"
    assert len(FRONTIER_MODELS) > 0, "FRONTIER_MODELS must not be empty"
