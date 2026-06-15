"""Unit tests for src/pi_call.py."""
import os
import sys
from unittest.mock import patch

import pytest

# Ensure the src/ directory is on the import path so `pi_call` can be imported
# regardless of how pytest is invoked.
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"),
)

from pi_call import (  # noqa: E402  (path-injection above)
    _provider_model,
    pi_call,
    BUDGET_MODELS,
    FRONTIER_MODELS,
)


class TestProviderModel:
    """Tests for the _provider_model helper that splits 'provider/model'."""

    def test_tokenrouter_model(self):
        """'tokenrouter/MiniMax-M3' -> ('tokenrouter', 'MiniMax-M3')."""
        provider, model = _provider_model("tokenrouter/MiniMax-M3")
        assert provider == "tokenrouter"
        assert model == "MiniMax-M3"

    def test_anthropic_model(self):
        """'anthropic/claude-sonnet-4-6' -> ('anthropic', 'claude-sonnet-4-6')."""
        provider, model = _provider_model("anthropic/claude-sonnet-4-6")
        assert provider == "anthropic"
        assert model == "claude-sonnet-4-6"


class TestPiCallAvailability:
    """Tests for pi_call when the `pi` CLI is not installed on the system."""

    @patch(
        "pi_call.subprocess.run",
        side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'pi'"),
    )
    def test_raises_runtime_error_when_pi_missing_and_provider_is_anthropic(
        self, _mock_run
    ):
        """Anthropic provider + no pi binary -> RuntimeError."""
        with pytest.raises(RuntimeError):
            pi_call("anthropic/claude-sonnet-4-6", "Hello, world!")

    @patch(
        "pi_call.subprocess.run",
        side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'pi'"),
    )
    def test_raises_runtime_error_when_pi_missing_and_provider_is_openai(
        self, _mock_run
    ):
        """Any non-tokenrouter provider + no pi binary -> RuntimeError."""
        with pytest.raises(RuntimeError):
            pi_call("openai/gpt-4o", "Tell me a joke.")


class TestModelLists:
    """Tests for the exported model-list constants."""

    def test_budget_models_is_non_empty_list(self):
        assert isinstance(BUDGET_MODELS, list)
        assert len(BUDGET_MODELS) > 0

    def test_frontier_models_is_non_empty_list(self):
        assert isinstance(FRONTIER_MODELS, list)
        assert len(FRONTIER_MODELS) > 0
