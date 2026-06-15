"""Unit tests for src/pi_call.py."""
import os
import subprocess
import sys
from unittest.mock import patch

import pytest

# Make the src/ package importable when running pytest from the project root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from pi_call import (  # noqa: E402
    BUDGET_MODELS,
    FRONTIER_MODELS,
    _provider_model,
    pi_call,
)


# ---------------------------------------------------------------------------
# _provider_model
# ---------------------------------------------------------------------------
class TestProviderModel:
    """Tests for the _provider_model string-parsing helper."""

    def test_tokenrouter_model(self):
        """'tokenrouter/MiniMax-M3' → ('tokenrouter', 'MiniMax-M3')."""
        assert _provider_model("tokenrouter/MiniMax-M3") == (
            "tokenrouter",
            "MiniMax-M3",
        )

    def test_anthropic_model(self):
        """'anthropic/claude-sonnet-4-6' → ('anthropic', 'claude-sonnet-4-6')."""
        assert _provider_model("anthropic/claude-sonnet-4-6") == (
            "anthropic",
            "claude-sonnet-4-6",
        )


# ---------------------------------------------------------------------------
# BUDGET_MODELS / FRONTIER_MODELS
# ---------------------------------------------------------------------------
class TestModelCatalogs:
    """Tests for the exported BUDGET_MODELS and FRONTIER_MODELS constants."""

    def test_budget_models_is_non_empty_list(self):
        assert isinstance(BUDGET_MODELS, list), "BUDGET_MODELS must be a list"
        assert len(BUDGET_MODELS) > 0, "BUDGET_MODELS must not be empty"

    def test_frontier_models_is_non_empty_list(self):
        assert isinstance(FRONTIER_MODELS, list), "FRONTIER_MODELS must be a list"
        assert len(FRONTIER_MODELS) > 0, "FRONTIER_MODELS must not be empty"


# ---------------------------------------------------------------------------
# pi_call — RuntimeError when the local 'pi' binary is unavailable
# ---------------------------------------------------------------------------
class TestPiCallAvailability:
    """pi_call must raise RuntimeError when 'pi' is missing and the
    requested provider is not 'tokenrouter'."""

    @patch("pi_call.subprocess.run")
    def test_raises_runtime_error_when_pi_unavailable(self, mock_run):
        # Simulate the 'pi' executable not being installed / not on PATH.
        # subprocess.run raises FileNotFoundError when the binary is absent.
        mock_run.side_effect = FileNotFoundError(
            "[Errno 2] No such file or directory: 'pi'"
        )

        with pytest.raises(RuntimeError):
            pi_call("anthropic/claude-sonnet-4-6", "Hello from the test suite")

    @patch("pi_call.subprocess.run")
    def test_does_not_swallow_called_process_error(self, mock_run):
        # A non-zero exit from a real 'pi' should also surface as an error,
        # not be silently swallowed by the missing-binary branch.
        err = subprocess.CalledProcessError(
            returncode=127,
            cmd=["pi", "--version"],
            output=b"",
            stderr=b"pi: command not found",
        )
        mock_run.side_effect = err

        with pytest.raises((RuntimeError, subprocess.CalledProcessError)):
            pi_call("anthropic/claude-sonnet-4-6", "ping")
