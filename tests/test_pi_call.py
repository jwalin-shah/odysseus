"""Unit tests for src.pi_call.

Covers:
- _provider_model parsing
- pi_call error path when the `pi` CLI is unavailable
- BUDGET_MODELS / FRONTIER_MODELS sanity
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.pi_call import (
    BUDGET_MODELS,
    FRONTIER_MODELS,
    _provider_model,
    pi_call,
)


# --------------------------------------------------------------------------- #
# _provider_model                                                              #
# --------------------------------------------------------------------------- #

class TestProviderModel:
    def test_tokenrouter_model(self):
        assert _provider_model("tokenrouter/MiniMax-M3") == (
            "tokenrouter",
            "MiniMax-M3",
        )

    def test_anthropic_model(self):
        assert _provider_model("anthropic/claude-sonnet-4-6") == (
            "anthropic",
            "claude-sonnet-4-6",
        )

    def test_unknown_provider_defaults_gracefully(self):
        # Whatever the implementation chooses, it must not raise on a
        # well-formed "provider/model" string.
        provider, model = _provider_model("openai/gpt-4o")
        assert provider == "openai"
        assert model == "gpt-4o"

    def test_returns_tuple_of_two_strings(self):
        result = _provider_model("anthropic/claude-sonnet-4-6")
        assert isinstance(result, tuple)
        assert len(result) == 2
        assert all(isinstance(x, str) for x in result)


# --------------------------------------------------------------------------- #
# pi_call — error path when `pi` CLI is unavailable                           #
# --------------------------------------------------------------------------- #

class TestPiCallUnavailable:
    """Simulate the `pi` binary being missing or failing."""

    def test_raises_runtime_error_when_pi_missing_anthropic(self):
        mock_result = MagicMock()
        mock_result.returncode = 127  # classic "command not found"
        mock_result.stdout = ""
        mock_result.stderr = "pi: command not found"

        with patch("src.pi_call.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError):
                pi_call("anthropic/claude-sonnet-4-6", prompt="hello")

    def test_raises_runtime_error_when_pi_missing_openai(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "pi: error"

        with patch("src.pi_call.subprocess.run", return_value=mock_result):
            with pytest.raises(RuntimeError):
                pi_call("openai/gpt-4o", prompt="hi")

    def test_raises_runtime_error_when_subprocess_raises(self):
        # subprocess.run itself raising (e.g. FileNotFoundError on POSIX,
        # NotImplementedError on Windows for shell=True, etc.)
        with patch(
            "src.pi_call.subprocess.run",
            side_effect=FileNotFoundError("pi not on PATH"),
        ):
            with pytest.raises(RuntimeError):
                pi_call("anthropic/claude-sonnet-4-6", prompt="hello")

    def test_does_not_raise_for_tokenrouter_when_pi_missing(self):
        """The tokenrouter path should bypass the `pi` CLI entirely."""
        # If implementation routes tokenrouter to a different backend,
        # mocking subprocess.run with a "failure" must not blow it up.
        mock_result = MagicMock()
        mock_result.returncode = 127
        mock_result.stdout = ""
        mock_result.stderr = "pi: command not found"

        with patch("src.pi_call.subprocess.run", return_value=mock_result):
            # Should NOT raise RuntimeError
            try:
                pi_call("tokenrouter/MiniMax-M3", prompt="hello")
            except RuntimeError as exc:
                pytest.fail(
                    f"tokenrouter path should not depend on the `pi` CLI, "
                    f"but raised RuntimeError: {exc}"
                )


# --------------------------------------------------------------------------- #
# BUDGET_MODELS / FRONTIER_MODELS                                              #
# --------------------------------------------------------------------------- #

class TestModelLists:
    def test_budget_models_is_non_empty_list(self):
        assert isinstance(BUDGET_MODELS, list), "BUDGET_MODELS must be a list"
        assert len(BUDGET_MODELS) > 0, "BUDGET_MODELS must not be empty"

    def test_frontier_models_is_non_empty_list(self):
        assert isinstance(FRONTIER_MODELS, list), "FRONTIER_MODELS must be a list"
        assert len(FRONTIER_MODELS) > 0, "FRONTIER_MODELS must not be empty"

    def test_budget_models_entries_are_strings(self):
        for entry in BUDGET_MODELS:
            assert isinstance(entry, str), f"Expected str, got {type(entry)!r}"

    def test_frontier_models_entries_are_strings(self):
        for entry in FRONTIER_MODELS:
            assert isinstance(entry, str), f"Expected str, got {type(entry)!r}"

    def test_model_lists_are_disjoint(self):
        """Budget and frontier tiers should not overlap."""
        overlap = set(BUDGET_MODELS) & set(FRONTIER_MODELS)
        assert not overlap, f"Models present in both tiers: {overlap}"

    @pytest.mark.parametrize("entry", BUDGET_MODELS)
    def test_budget_entries_parseable_by_provider_model(self, entry):
        provider, model = _provider_model(entry)
        assert provider and model, f"Could not parse BUDGET entry: {entry!r}"

    @pytest.mark.parametrize("entry", FRONTIER_MODELS)
    def test_frontier_entries_parseable_by_provider_model(self, entry):
        provider, model = _provider_model(entry)
        assert provider and model, f"Could not parse FRONTIER entry: {entry!r}"
