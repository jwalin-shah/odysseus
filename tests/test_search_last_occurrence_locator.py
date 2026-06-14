"""Tests for ``search_last_occurrence_locator``."""

from __future__ import annotations

import os
import sys

# Make the ``src`` package importable regardless of where pytest is invoked.
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from search_last_occurrence_locator import search_last_occurrence_locator  # noqa: E402


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------


def test_last_occurrence_of_repeated_value():
    """Repeated values return the *rightmost* index."""
    arr = [1, 2, 3, 4, 4, 4, 5, 6]
    assert search_last_occurrence_locator(arr, 4) == 5


def test_target_present_once_returns_its_index():
    """A single occurrence returns its exact index."""
    arr = [1, 2, 3, 4, 5]
    assert search_last_occurrence_locator(arr, 3) == 2


def test_target_absent_returns_minus_one():
    """A missing target yields ``-1``."""
    arr = [1, 2, 3, 4, 5]
    assert search_last_occurrence_locator(arr, 6) == -1


def test_target_smaller_than_minimum_returns_minus_one():
    """A target below the smallest element yields ``-1``."""
    arr = [10, 20, 30, 40, 50]
    assert search_last_occurrence_locator(arr, 5) == -1


def test_target_larger_than_maximum_returns_minus_one():
    """A target above the largest element yields ``-1``."""
    arr = [10, 20, 30, 40, 50]
    assert search_last_occurrence_locator(arr, 100) == -1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_array_returns_minus_one():
    """An empty array always returns ``-1``."""
    assert search_last_occurrence_locator([], 5) == -1


def test_all_identical_elements_return_last_index():
    """An array of identical elements returns the last index."""
    arr = [7, 7, 7, 7, 7]
    assert search_last_occurrence_locator(arr, 7) == 4


def test_target_is_first_element():
    """The first element is correctly identified when it matches."""
    arr = [1, 2, 2, 2, 3]
    assert search_last_occurrence_locator(arr, 1) == 0


def test_target_is_last_element():
    """The last element is correctly identified when it matches."""
    arr = [1, 2, 2, 2, 3]
    assert search_last_occurrence_locator(arr, 3) == 4


def test_single_element_array_match():
    """A single-element array with the target returns index 0."""
    assert search_last_occurrence_locator([5], 5) == 0


def test_single_element_array_no_match():
    """A single-element array without the target returns ``-1``."""
    assert search_last_occurrence_locator([5], 3) == -1


def test_works_with_strings():
    """Strings (and other comparable types) are supported."""
    arr = ["apple", "banana", "banana", "cherry", "date"]
    assert search_last_occurrence_locator(arr, "banana") == 2


def test_accepts_tuple_input():
    """Any :class:`Sequence` is accepted, including tuples."""
    assert search_last_occurrence_locator((1, 2, 2, 3), 2) == 2


def test_works_with_negative_numbers():
    """Negative values are located just like positive ones."""
    arr = [-10, -5, -5, -3, 0, 4]
    assert search_last_occurrence_locator(arr, -5) == 2


def test_does_not_mutate_input():
    """The function must not mutate its input sequence."""
    arr = [1, 2, 2, 2, 3]
    snapshot = list(arr)
    search_last_occurrence_locator(arr, 2)
    assert arr == snapshot