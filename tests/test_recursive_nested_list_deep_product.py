"""Tests for :func:`recursive_nested_list_deep_product`."""

import math

import pytest

from recursive_nested_list_deep_product import recursive_nested_list_deep_product


# ---------------------------------------------------------------------------
# Basic / edge cases
# ---------------------------------------------------------------------------

def test_empty_list_returns_one():
    """The empty list is the multiplicative identity: 1."""
    assert recursive_nested_list_deep_product([]) == 1


def test_only_empty_sublists_returns_one():
    """Empty containers nested anywhere still produce 1."""
    assert recursive_nested_list_deep_product([[], [[]], []]) == 1


def test_single_element_list():
    assert recursive_nested_list_deep_product([42]) == 42


def test_bare_number_is_returned_unchanged():
    """A bare numeric leaf is its own product."""
    assert recursive_nested_list_deep_product(7) == 7


# ---------------------------------------------------------------------------
# Flat and nested structures
# ---------------------------------------------------------------------------

def test_flat_list_of_integers():
    assert recursive_nested_list_deep_product([1, 2, 3, 4]) == 24


def test_one_level_nested():
    assert recursive_nested_list_deep_product([1, [2, 3], 4]) == 24


def test_deeply_nested_list():
    nested = [1, [2, [3, [4, [5]]]]]
    assert recursive_nested_list_deep_product(nested) == 120


def test_irregular_nesting():
    nested = [[1, 2], 3, [[4], [5, 6]], [[[7]]]]
    assert recursive_nested_list_deep_product(nested) == 5040  # 7!


# ---------------------------------------------------------------------------
# Sign, zero, and floating-point behaviour
# ---------------------------------------------------------------------------

def test_zero_anywhere_zeroes_product():
    assert recursive_nested_list_deep_product([1, [2, 0], 3]) == 0


def test_negative_numbers_multiply_correctly():
    assert recursive_nested_list_deep_product([-1, [-2, 3], -4]) == -24


def test_even_number_of_negatives_is_positive():
    assert recursive_nested_list_deep_product([-1, -2, [-3, -4]]) == 24


def test_floats_supported():
    result = recursive_nested_list_deep_product([0.5, [2.0, 4]])
    assert math.isclose(result, 4.0)


def test_mixed_int_and_float():
    result = recursive_nested_list_deep_product([2, [3.0, 4]])
    assert math.isclose(result, 24.0)
    assert isinstance(result, (int, float))


# ---------------------------------------------------------------------------
# Generosity of input handling
# ---------------------------------------------------------------------------

def test_tuples_are_treated_like_lists():
    assert recursive_nested_list_deep_product((1, 2, (3, 4))) == 24


def test_non_numeric_items_are_ignored():
    """Strings / ``None`` / custom objects must not break the helper."""
    assert recursive_nested_list_deep_product([1, "two", [3, None], 4]) == 12


def test_nested_with_booleans_are_ignored():
    """``True`` / ``False`` must NOT collapse to 1 / 0 in the product."""
    assert recursive_nested_list_deep_product([2, True, [3, False], 4]) == 24


# ---------------------------------------------------------------------------
# Parametrised sanity checks
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "structure, expected",
    [
        ([], 1),
        ([5], 5),
        ([1, 2, 3, 4, 5], 120),
        ([[1, 2], [3, 4]], 24),
        ([1, [2, [3, [4, [5]]]]], 120),
        ([-1, 1, -1, 1], 1),
        ([10, [0.1, [10]]], 10.0),
    ],
)
def test_parametrised_deep_product(structure, expected):
    assert math.isclose(
        recursive_nested_list_deep_product(structure),
        expected,
        rel_tol=1e-12,
    )