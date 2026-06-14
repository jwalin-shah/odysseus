"""Tests for :func:`search.last_occurrence_locator.last_occurrence_locator`."""

import os
import sys

# Make sure the project root is on the import path so the test module
# can import from the top-level ``search`` package regardless of where
# pytest is invoked from.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from search.last_occurrence_locator import last_occurrence_locator


# ---------------------------------------------------------------------------
# Core happy-path cases
# ---------------------------------------------------------------------------

def test_single_occurrence_in_middle():
    """Target appearing exactly once in the middle of a sorted array."""
    assert last_occurrence_locator([1, 3, 5, 7, 9], 5) == 2


def test_multiple_occurrences_returns_rightmost():
    """When duplicates exist, return the index of the *last* one."""
    assert last_occurrence_locator([1, 2, 2, 2, 3, 4], 2) == 3


def test_all_elements_equal_to_target():
    """Array consisting solely of the target returns the final index."""
    assert last_occurrence_locator([7, 7, 7, 7, 7], 7) == 4


def test_target_at_first_position():
    """When the very first element is the target, behaviour is correct."""
    assert last_occurrence_locator([2, 2, 2, 3, 4], 2) == 2


def test_target_at_last_position():
    """When the very last element is the target, its index is returned."""
    assert last_occurrence_locator([1, 2, 3, 4, 5], 5) == 4


# ---------------------------------------------------------------------------
# Negative / boundary cases
# ---------------------------------------------------------------------------

def test_target_not_present_returns_minus_one():
    """A target that does not exist in the array returns -1."""
    assert last_occurrence_locator([1, 2, 3, 4, 5], 6) == -1


def test_target_smaller_than_all_elements():
    """A target smaller than every element returns -1."""
    assert last_occurrence_locator([10, 20, 30, 40], 0) == -1


def test_target_larger_than_all_elements():
    """A target larger than every element returns -1."""
    assert last_occurrence_locator([10, 20, 30, 40], 99) == -1


def test_empty_array_returns_minus_one():
    """An empty sequence always returns -1."""
    assert last_occurrence_locator([], 1) == -1


def test_none_input_returns_minus_one():
    """``None`` is treated the same as an empty sequence."""
    assert last_occurrence_locator(None, 1) == -1


# ---------------------------------------------------------------------------
# Single-element arrays
# ---------------------------------------------------------------------------

def test_single_element_match():
    """Single element array, target present."""
    assert last_occurrence_locator([5], 5) == 0


def test_single_element_no_match():
    """Single element array, target absent."""
    assert last_occurrence_locator([5], 3) == -1


# ---------------------------------------------------------------------------
# Element type variations
# ---------------------------------------------------------------------------

def test_works_with_strings():
    """Strings sorted lexicographically are handled correctly."""
    assert last_occurrence_locator(['a', 'b', 'b', 'c', 'd'], 'b') == 2


def test_works_with_floats():
    """Floating point values are supported as well."""
    arr = [0.1, 0.2, 0.2, 0.3, 0.4]
    assert last_occurrence_locator(arr, 0.2) == 2


def test_works_with_negative_numbers():
    """Negative numbers do not break the comparison logic."""
    arr = [-5, -3, -3, -1, 0, 2]
    assert last_occurrence_locator(arr, -3) == 2


# ---------------------------------------------------------------------------
# Result-type sanity checks
# ---------------------------------------------------------------------------

def test_return_type_is_int():
    """The function must always return a plain ``int``."""
    result = last_occurrence_locator([1, 2, 3], 2)
    assert isinstance(result, int)
    assert not isinstance(result, bool)  # guard against ``True``/``False``


def test_does_not_mutate_input():
    """The input list must remain unchanged after the call."""
    arr = [1, 2, 2, 3, 4, 5, 5, 5]
    snapshot = arr.copy()
    last_occurrence_locator(arr, 5)
    assert arr == snapshot


@pytest.mark.parametrize(
    "arr, target, expected",
    [
        ([1, 2, 3, 4, 5], 1, 0),
        ([1, 2, 3, 4, 5], 5, 4),
        ([1, 2, 2, 3, 3, 3, 4], 2, 2),
        ([1, 2, 2, 3, 3, 3, 4], 3, 5),
        ([0, 0, 0, 0], 0, 3),
        ([1, 2, 3], 4, -1),
        ([1, 2, 3], 0, -1),
    ],
)
def test_parametrized_cases(arr, target, expected):
    """A handful of representative cases evaluated together."""
    assert last_occurrence_locator(arr, target) == expected