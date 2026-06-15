"""Unit tests for src/pi_call.py."""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Make src importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pi_call  # noqa: E402
from pi_call import _provider_model, pi_call, BUDGET_MODELS, FRONTIER_MODELS  # noqa: E402


# ---------------------------------------------------------------------------
# _provider_model
# ---------------------------------------------------------------------------

def test_provider_model_tokenrouter_minimax():
    """_provider_model splits 'tokenrouter/MiniMax-M3' correctly."""
    assert _provider_model("tokenrouter/MiniMax-M3") == ("tokenrouter", "MiniMax-M3")


def test_provider_model_anthropic_claude():
    """_provider_model splits 'anthropic/claude-sonnet-4-6' correctly."""
    assert _provider_model("anthropic/claude-sonnet-4-6") == ("anthropic", "claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# pi_call error handling
# ---------------------------------------------------------------------------

def test_pi_call_raises_when_pi_unavailable_and_provider_not_tokenrouter():
    """pi_call must raise RuntimeError when 'pi' is missing and provider != tokenrouter."""
    # Simulate the `pi` binary not being on PATH: subprocess.run raises FileNotFoundError
    with patch.object(pi_call.subprocess, "run",
                      side_effect=FileNotFoundError("pi not found")):
        with pytest.raises(RuntimeError) as excinfo:
            pi_call(prompt="hello", model="anthropic/claude-sonnet-4-6")
    # The error message should reference the missing binary or the fallback provider
    assert "pi" in str(excinfo.value).lower() or "tokenrouter" in str(excinfo.value).lower()


def test_pi_call_raises_when_pi_unavailable_tokenrouter_path():
    """For tokenrouter provider, an unhandled error from subprocess should also bubble up
    (or at least not silently succeed) — here we assert it raises when pi is missing."""
    with patch.object(pi_call.subprocess, "run",
                      side_effect=FileNotFoundError("pi not found")):
        with pytest.raises(Exception):
            # The tokenrouter path may attempt to use an HTTP fallback; we just
            # assert that *some* exception is surfaced rather than silent success.
            pi_call(prompt="hello", model="tokenrouter/MiniMax-M3")


def test_pi_call_raises_when_pi_returns_nonzero_and_provider_not_tokenrouter():
    """If the `pi` subprocess returns a non-zero exit code and provider != tokenrouter,
    pi_call should raise RuntimeError."""
    fake = MagicMock()
    fake.returncode = 1
    fake.stdout = ""
    fake.stderr = "boom"
    with patch.object(pi_call.subprocess, "run", return_value=fake):
        with pytest.raises(RuntimeError):
            pi_call(prompt="hello", model="anthropic/claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# Model lists
# ---------------------------------------------------------------------------

def test_budget_models_non_empty_list_of_strings():
    assert isinstance(BUDGET_MODELS, list)
    assert len(BUDGET_MODELS) > 0
    assert all(isinstance(m, str) and m for m in BUDGET_MODELS)


def test_frontier_models_non_empty_list_of_strings():
    assert isinstance(FRONTIER_MODELS, list)
    assert len(FRONTIER_MODELS) > 0
    assert all(isinstance(m, str) and m for m in FRONTIER_MODELS)


def test_budget_and_frontier_models_are_disjoint():
    """BUDGET and FRONTIER tiers should not overlap."""
    assert set(BUDGET_MODELS).isdisjoint(set(FRONTIER_MODELS))
