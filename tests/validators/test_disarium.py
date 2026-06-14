"""Tests for :mod:`validators.disarium`."""
import sys
from pathlib import Path

import pytest

# Ensure the project root is on ``sys.path`` so ``validators.disarium`` is
# importable regardless of how/where pytest is invoked.
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from validators.disarium import is_disarium, disarium  # noqa: E402


# ---------------------------------------------------------------------------
# Single-digit numbers are trivially Disarium (d^1 == d).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
def test_single_digit_numbers_are_disarium(n):
    assert is_disarium(n) is True


# ---------------------------------------------------------------------------
# Well-known Disarium numbers (verified by hand).
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "n",
    [
        89,    # 8^1 + 9^2 = 8 + 81 = 89
        135,   # 1^1 + 3^2 + 5^3 = 1 + 9 + 125 = 135
        175,   # 1^1 + 7^2 + 5^3 = 1 + 49 + 125 = 175
        518,   # 5^1 + 1^2 + 8^3 = 5 + 1 + 512 = 518
        598,   # 5^1 + 9^2 + 8^3 = 5 + 81 + 512 = 598
        1306,  # 1 + 9 + 0 + 1296 = 1306
        1676,  # 1 + 36 + 343 + 1296 = 1676
        2427,  # 2 + 16 + 8 + 2401 = 2427
    ],
)
def test_known_disarium_numbers(n):
    assert is_disarium(n) is True


# ---------------------------------------------------------------------------
# Numbers that are NOT Disarium.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "n",
    [10, 11, 12, 20, 50, 100, 200, 999, 1000, 1234, 5678, 9999, 10000],
)
def test_non_disarium_numbers(n):
    assert is_disarium(n) is False


def test_negative_numbers_are_not_disarium():
    assert is_disarium(-1) is False
    assert is_disarium(-89) is False
    assert is_disarium(-135) is False
    assert is_disarium(-1000) is False


# ---------------------------------------------------------------------------
# Type validation.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad",
    [1.5, 0.0, 89.0, "89", "135", "", None, [89], (89,), {89: 1}, object()],
)
def test_non_integer_raises_type_error(bad):
    with pytest.raises(TypeError):
        is_disarium(bad)


@pytest.mark.parametrize("bad", [True, False])
def test_bool_is_rejected(bad):
    with pytest.raises(TypeError):
        is_disarium(bad)


# ---------------------------------------------------------------------------
# Module-level alias.
# ---------------------------------------------------------------------------

def test_module_alias_matches_function():
    assert disarium is is_disarium
    assert disarium(89) is True
    assert disarium(10) is False