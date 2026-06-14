"""Tests for ``stats.gini``."""

from __future__ import annotations

import math
import os
import sys
import random

import pytest

# Make the project root importable so ``from stats.gini import gini`` works
# regardless of how pytest is invoked.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from stats.gini import gini  # noqa: E402


# ---------------------------------------------------------------------------
# Basic / boundary cases
# ---------------------------------------------------------------------------


def test_perfect_equality_returns_zero():
    """All values equal -> Gini = 0."""
    assert gini([5, 5, 5, 5, 5]) == 0.0
    assert gini([1, 1, 1]) == 0.0
    assert gini([42.5, 42.5, 42.5, 42.5]) == 0.0


def test_single_value_returns_zero():
    """A single value is trivially equal to itself -> Gini = 0."""
    assert gini([100]) == 0.0
    assert gini([0]) == 0.0


def test_two_equal_values_returns_zero():
    assert gini([7, 7]) == 0.0


def test_all_zeros_returns_zero():
    """All-zero input should not raise (no total to divide by) and returns 0."""
    assert gini([0, 0, 0, 0]) == 0.0
    assert gini([0]) == 0.0


# ---------------------------------------------------------------------------
# Known analytical results
# ---------------------------------------------------------------------------


def test_two_unequal_values_known_value():
    """For two values [a, b] with a <= b: Gini = (b - a) / (2 * (a + b))."""
    assert math.isclose(gini([0, 1]), 0.5, rel_tol=1e-9)
    assert math.isclose(gini([3, 7]), 0.2, rel_tol=1e-9)
    assert math.isclose(gini([1, 2]), 1.0 / 6.0, rel_tol=1e-9)


def test_perfect_inequality_extreme_case():
    """One of n values owns everything, the rest have 0 -> Gini = (n-1)/n."""
    for n in (2, 3, 5, 10, 20):
        values = [0] * (n - 1) + [1]
        assert math.isclose(gini(values), (n - 1) / n, rel_tol=1e-9), n


def test_wikipedia_canonical_example():
    """The classic textbook example: [3, 3, 4, 5, 5, 6, 7, 10] ~ 0.218."""
    values = [3, 3, 4, 5, 5, 6, 7, 10]
    assert math.isclose(gini(values), 0.218, abs_tol=1e-3)


# ---------------------------------------------------------------------------
# Invariance / monotonicity properties
# ---------------------------------------------------------------------------


def test_invariant_under_positive_scaling():
    """Multiplying all values by the same positive constant preserves Gini."""
    base = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    g_base = gini(base)
    assert math.isclose(g_base, gini([x * 1000 for x in base]), rel_tol=1e-9)
    assert math.isclose(g_base, gini([x * 0.0001 for x in base]), rel_tol=1e-9)


def test_independent_of_input_order():
    """Reordering the input list must not change the result."""
    base = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    g_base = gini(base)
    assert math.isclose(g_base, gini(list(reversed(base))), rel_tol=1e-9)
    scrambled = [7, 2, 10, 1, 9, 4, 8, 3, 6, 5]
    assert math.isclose(g_base, gini(scrambled), rel_tol=1e-9)


def test_inequality_ordering():
    """Making the distribution more unequal must not decrease Gini."""
    g_equal = gini([5, 5, 5, 5, 5])
    g_mild = gini([4, 5, 5, 5, 6])
    g_extreme = gini([0, 0, 0, 0, 25])
    assert g_equal <= g_mild <= g_extreme


# ---------------------------------------------------------------------------
# Error / edge handling
# ---------------------------------------------------------------------------


def test_empty_list_raises_value_error():
    with pytest.raises(ValueError):
        gini([])


def test_negative_values_raise_value_error():
    with pytest.raises(ValueError):
        gini([1, 2, -3, 4])


def test_non_numeric_element_raises_type_error():
    with pytest.raises(TypeError):
        gini([1, 2, "three", 4])


def test_non_sequence_input_raises_type_error():
    with pytest.raises(TypeError):
        gini("not a list")
    with pytest.raises(TypeError):
        gini(123)


# ---------------------------------------------------------------------------
# Robustness / range checks
# ---------------------------------------------------------------------------


def test_result_always_in_unit_interval():
    """For any non-negative numeric input, Gini must be in [0, 1]."""
    rng = random.Random(2024)
    for _ in range(25):
        n = rng.randint(2, 200)
        values = [rng.uniform(0.0, 1000.0) for _ in range(n)]
        g = gini(values)
        assert 0.0 <= g <= 1.0, f"Gini out of range ({g}) for n={n}"


def test_accepts_tuple_input():
    """Tuples should behave the same as lists."""
    assert math.isclose(
        gini((1, 2, 3, 4, 5)),
        gini([1, 2, 3, 4, 5]),
        rel_tol=1e-9,
    )


def test_accepts_mixed_int_and_float():
    """Mixing ints and floats is fine; the result is still a float."""
    result = gini([1, 2, 3, 4, 5.0])
    assert isinstance(result, float)
    assert 0.0 <= result <= 1.0