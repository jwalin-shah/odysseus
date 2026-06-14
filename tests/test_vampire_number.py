"""Tests for ``vampire_number``."""

import os
import sys

# Make the project root importable when this file is run directly
# (e.g. ``python tests/test_vampire_number.py``).
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import pytest

from vampire_number import vampire_number


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_valid_vampire(n, fangs):
    """Return ``True`` iff ``(x, y) = fangs`` is a valid vampire split."""
    if fangs is None:
        return False
    x, y = fangs
    s = str(n)
    if len(s) % 2 != 0:
        return False
    k = len(s) // 2
    if len(str(x)) != k or len(str(y)) != k:
        return False
    if str(x).endswith('0') and str(y).endswith('0'):
        return False
    if x * y != n:
        return False
    return sorted(s) == sorted(str(x) + str(y))


# ---------------------------------------------------------------------------
# Known vampire numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "n, expected_fangs",
    [
        (1260, {21, 60}),
        (1395, {15, 93}),
        (1435, {35, 41}),
        (1530, {30, 51}),
        (1827, {21, 87}),
        (2187, {27, 81}),
        (6880, {80, 86}),
    ],
)
def test_known_4_digit_vampires(n, expected_fangs):
    """All seven known 4-digit vampire numbers are detected correctly."""
    result = vampire_number(n)
    assert result is not None, f"{n} should be a vampire number"
    assert set(result) == expected_fangs
    assert _is_valid_vampire(n, result)


def test_6_digit_vampire_102510():
    """102510 = 201 * 510 is a 6-digit vampire number."""
    result = vampire_number(102510)
    assert result is not None
    assert _is_valid_vampire(102510, result)
    assert set(result) == {201, 510}


def test_fangs_returned_in_sorted_order():
    """Fangs are always returned with the smaller element first."""
    for n in [1260, 1395, 1435, 1530, 1827, 2187, 6880, 102510]:
        result = vampire_number(n)
        assert result is not None
        x, y = result
        assert x <= y, f"fangs of {n} not sorted: {result}"


# ---------------------------------------------------------------------------
# Negative / edge cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [1255, 1000, 1001, 1234, 1500])
def test_not_vampire(n):
    """These even-digit-count numbers are not vampire numbers."""
    assert vampire_number(n) is None


def test_zero_is_not_vampire():
    """Zero is not a vampire number."""
    assert vampire_number(0) is None


def test_negative_is_not_vampire():
    """Negative numbers are not vampire numbers."""
    assert vampire_number(-1260) is None
    assert vampire_number(-1) is None


@pytest.mark.parametrize("n", [1, 123, 12345, 1234567])
def test_odd_digit_count(n):
    """Numbers with an odd digit count can never be vampire numbers."""
    assert vampire_number(n) is None


def test_non_integer_input():
    """Non-integer (and boolean) inputs are rejected with ``None``."""
    assert vampire_number("1260") is None
    assert vampire_number(1260.5) is None
    assert vampire_number(None) is None
    assert vampire_number([1260]) is None
    # Booleans are technically a subclass of int in Python; they should
    # still be rejected to keep the public API strict.
    assert vampire_number(True) is None
    assert vampire_number(False) is None