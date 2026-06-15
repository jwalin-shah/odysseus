"""Unit tests for src.pi_call."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Make src/ importable when running from the repo root.
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from pi_call import (  # noqa: E402
    _provider_model,
    pi_call,
    BUDGET_MODELS,
    FRONTIER_MODELS,
)


# --------------------------------------------------------------------------- #
# _provider_model
# --------------------------------------------------------------------------- #
class TestProviderModel:
    def test_tokenrouter_prefix_is_split(self):
        assert _provider_model("tokenrouter/MiniMax-M3") == ("tokenrouter", "MiniMax-M3")

    def test_anthropic_prefix_is_split(self):
        assert _provider_model("anthropic/claude-sonnet-4-6") == ("anthropic", "claude-sonnet-4-6")


# --------------------------------------------------------------------------- #
# Model catalogues
# --------------------------------------------------------------------------- #
class TestModelCatalog:
    def test_budget_models_is_a_non_empty_list(self):
        assert isinstance(BUDGET_MODELS, list), "BUDGET_MODELS must be a list"
        assert len(BUDGET_MODELS) > 0, "BUDGET_MODELS must not be empty"

    def test_frontier_models_is_a_non_empty_list(self):
        assert isinstance(FRONTIER_MODELS, list), "FRONTIER_MODELS must be a list"
        assert len(FRONTIER_MODELS) > 0, "FRONTIER_MODELS must not be empty"


# --------------------------------------------------------------------------- #
# pi_call — error path when the `pi` CLI is missing
# --------------------------------------------------------------------------- #
class TestPiCallWhenPiMissing:
    def test_runtime_error_when_pi_unavailable_for_non_tokenrouter(self):
        """A missing `pi` binary must surface as RuntimeError, not a crash."""
        # The OS raises FileNotFoundError(ENOENT) when an executable is absent;
        # mock that to simulate "pi not installed / not on PATH".
        with patch(
            "pi_call.subprocess.run",
            side_effect=FileNotFoundError(2, "No such file or directory: 'pi'"),
        ):
            with pytest.raises(RuntimeError):
                pi_call("anthropic/claude-sonnet-4-6", prompt="hello")
