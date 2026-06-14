"""Tests for :mod:`validators.happy_number`."""

from __future__ import annotations

import os
import sys

import pytest

# Make the repository root importable so that ``validators`` resolves
# regardless of where pytest is invoked from.
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from validators.happy_number import is_happy, happy_number  # noqa: E402


# ---------------------------------------------------------------------------
# Happy numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "n",
    [
        1,
        7,
        10,
        13,
        19,
        23,
        28,
        31,
        32,
        44,
        49,
        68,
        70,
        79,
        82,
        86,
        91,
        94,
        97,
        100,
    ],
)
def test_known_happy_numbers(n):
    assert is_happy(n) is True


def test_one_is_happy():
    assert is_happy(1) is True


def test_seven_is_happy():
    # 7 -> 49 -> 97 -> 130 -> 10 -> 1
    assert is_happy(7) is True


def test_nineteen_is_happy():
    # Classic example from the Wikipedia article.
    # 19 -> 82 -> 68 -> 100 -> 1
    assert is_happy(19) is True


def test_large_powers_of_ten_are_happy():
    assert is_happy(1000) is True
    assert is_happy(10000) is True
    assert is_happy(10**12) is True


# ---------------------------------------------------------------------------
# Unhappy numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "n",
    [
        2,
        3,
        4,
        5,
        6,
        8,
        9,
        11,
        12,
        14,
        15,
        16,
        17,
        18,
        20,
        21,
        22,
        24,
        25,
        26,
        27,
        29,
        30,
        33,
    ],
)
def test_known_unhappy_numbers(n):
    assert is_happy(n) is False


def test_zero_is_unhappy():
    # 0 -> 0 forever, never reaches 1.
    assert is_happy(0) is False


def test_large_unhappy_number():
    # 999 -> 243 -> 29 -> ... falls into the 4 -> 16 -> 37 -> ... cycle.
    assert is_happy(999) is False
    assert is_happy(2_000_000) is False


# ---------------------------------------------------------------------------
# Edge cases / input validation
# ---------------------------------------------------------------------------

def test_negative_raises_value_error():
    with pytest.raises(ValueError):
        is_happy(-1)
    with pytest.raises(ValueError):
        is_happy(-19)


def test_float_raises_type_error():
    with pytest.raises(TypeError):
        is_happy(1.5)
    with pytest.raises(TypeError):
        is_happy(19.0)


def test_string_raises_type_error():
    with pytest.raises(TypeError):
        is_happy("19")
    with pytest.raises(TypeError):
        is_happy("")


def test_none_raises_type_error():
    with pytest.raises(TypeError):
        is_happy(None)


def test_bool_raises_type_error():
    # ``True`` and ``False`` are technically ``int`` instances; treat them
    # as invalid input rather than letting the implementation accept them
    # silently as 1 or 0.
    with pytest.raises(TypeError):
        is_happy(True)
    with pytest.raises(TypeError):
        is_happy(False)


def test_complex_raises_type_error():
    with pytest.raises(TypeError):
        is_happy(complex(1, 0))


def test_list_raises_type_error():
    with pytest.raises(TypeError):
        is_happy([19])


# ---------------------------------------------------------------------------
# API contract
# ---------------------------------------------------------------------------

def test_return_type_is_bool():
    assert isinstance(is_happy(19), bool)
    assert isinstance(is_happy(2), bool)


def test_happy_number_alias_matches_is_happy():
    """The module should expose a ``happy_number`` alias for symmetry."""
    assert happy_number is is_happy
    assert happy_number(19) is True
    assert happy_number(2) is False