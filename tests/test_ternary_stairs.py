"""Tests for :func:`ternary_stairs`."""

import pytest

from ternary_stairs import ternary_stairs


# ---------------------------------------------------------------------------
# Base cases
# ---------------------------------------------------------------------------


def test_zero_stairs():
    """f(0) = 1 (the empty sequence of moves is the only way to be at 0)."""
    assert ternary_stairs(0) == 1


def test_one_stair():
    """f(1) = 1 (only a single 1-step move works)."""
    assert ternary_stairs(1) == 1


def test_two_stairs():
    """f(2) = 2: (1+1) or (2)."""
    assert ternary_stairs(2) == 2


# ---------------------------------------------------------------------------
# Recurrence-derived values
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "n, expected",
    [
        (3, 4),    # 1+1+1, 1+2, 2+1, 3
        (4, 7),    # f(3)+f(2)+f(1) = 4+2+1
        (5, 13),   # 7+4+2
        (6, 24),   # 13+7+4
        (7, 44),   # 24+13+7
        (8, 81),   # 44+24+13
        (9, 149),  # 81+44+24
        (10, 274), # 149+81+44
    ],
)
def test_known_values(n, expected):
    """Hand-computed values for small n must match the function output."""
    assert ternary_stairs(n) == expected


# ---------------------------------------------------------------------------
# Property: the recurrence f(n) = f(n-1) + f(n-2) + f(n-3) holds for n >= 3
# ---------------------------------------------------------------------------


def test_recurrence_holds_for_range():
    """For every n in [3, 25] the recurrence relation must hold."""
    for n in range(3, 26):
        assert ternary_stairs(n) == (
            ternary_stairs(n - 1) + ternary_stairs(n - 2) + ternary_stairs(n - 3)
        ), f"Recurrence failed at n={n}"


# ---------------------------------------------------------------------------
# Edge cases & error handling
# ---------------------------------------------------------------------------


def test_negative_input_returns_zero():
    """A negative number of stairs has zero valid climbing sequences."""
    assert ternary_stairs(-1) == 0
    assert ternary_stairs(-7) == 0
    assert ternary_stairs(-100) == 0


def test_returns_python_int():
    """The result must be a plain ``int`` (so it composes with big integers)."""
    result = ternary_stairs(35)
    assert isinstance(result, int)
    # No floating-point or numpy artifacts.
    assert not isinstance(result, bool)


def test_monotonically_increasing():
    """f(n) is strictly increasing for n >= 1."""
    prev = ternary_stairs(1)
    for n in range(2, 20):
        curr = ternary_stairs(n)
        assert curr > prev, f"f({n})={curr} should be > f({n-1})={prev}"
        prev = curr


def test_invalid_type_raises():
    """Non-integer inputs must raise ``TypeError``."""
    with pytest.raises(TypeError):
        ternary_stairs(3.0)        # float, not int
    with pytest.raises(TypeError):
        ternary_stairs("5")        # string
    with pytest.raises(TypeError):
        ternary_stairs(None)       # None
    with pytest.raises(TypeError):
        ternary_stairs([1, 2, 3])  # list


# ---------------------------------------------------------------------------
# Larger value: verifies O(1)-space loop scales without regression.
# ---------------------------------------------------------------------------


def test_large_value_matches_recurrence():
    """f(50) should equal f(49) + f(48) + f(47) (self-consistency)."""
    a = ternary_stairs(50)
    b = ternary_stairs(49) + ternary_stairs(48) + ternary_stairs(47)
    assert a == b
    # And the result should be a positive integer.
    assert a > 0