"""Tests for :func:`search_leftmost_not_less_than` (lower-bound search)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the src/ directory importable when tests are run from the repo root
# without an installed package.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from search_leftmost_not_less_than import search_leftmost_not_less_than  # noqa: E402


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------

def test_target_present_in_middle():
    arr = [1, 3, 5, 7, 9]
    # 5 is present; we must return its leftmost occurrence.
    assert search_leftmost_not_less_than(arr, 5) == 2


def test_target_equals_first_element():
    arr = [1, 3, 5, 7, 9]
    assert search_leftmost_not_less_than(arr, 1) == 0


def test_target_equals_last_element():
    arr = [1, 3, 5, 7, 9]
    assert search_leftmost_not_less_than(arr, 9) == 4


def test_target_between_elements_returns_insertion_point():
    arr = [1, 3, 5, 7, 9]
    # 4 is not present; insertion point is between 3 and 5.
    assert search_leftmost_not_less_than(arr, 4) == 2
    # 6 is not present; insertion point is between 5 and 7.
    assert search_leftmost_not_less_than(arr, 6) == 3


def test_target_smaller_than_all_returns_zero():
    arr = [2, 4, 6, 8, 10]
    assert search_leftmost_not_less_than(arr, 0) == 0
    assert search_leftmost_not_less_than(arr, 1) == 0


def test_target_larger_than_all_returns_length():
    arr = [2, 4, 6, 8, 10]
    assert search_leftmost_not_less_than(arr, 11) == 5
    assert search_leftmost_not_less_than(arr, 100) == 5


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_array_returns_zero():
    assert search_leftmost_not_less_than([], 0) == 0
    assert search_leftmost_not_less_than([], -100) == 0
    assert search_leftmost_not_less_than([], 100) == 0


def test_single_element_array_target_smaller():
    assert search_leftmost_not_less_than([5], 1) == 0


def test_single_element_array_target_equal():
    assert search_leftmost_not_less_than([5], 5) == 0


def test_single_element_array_target_larger():
    assert search_leftmost_not_less_than([5], 10) == 1


# ---------------------------------------------------------------------------
# Duplicates: the "leftmost" requirement is the whole point
# ---------------------------------------------------------------------------

def test_duplicates_returns_leftmost_occurrence():
    arr = [1, 2, 2, 2, 3, 4, 5]
    # The first 2 lives at index 1.
    assert search_leftmost_not_less_than(arr, 2) == 1


def test_all_duplicates_of_target():
    arr = [4, 4, 4, 4, 4]
    assert search_leftmost_not_less_than(arr, 4) == 0
    assert search_leftmost_not_less_than(arr, 3) == 0
    assert search_leftmost_not_less_than(arr, 5) == 5


def test_target_just_below_repeated_value():
    arr = [1, 3, 3, 3, 5]
    # Searching for 3 should hit the first 3 (index 1), not any later one.
    assert search_leftmost_not_less_than(arr, 3) == 1
    # Searching for 2 (between 1 and the first 3) should land at index 1.
    assert search_leftmost_not_less_than(arr, 2) == 1


# ---------------------------------------------------------------------------
# Sequence types other than list
# ---------------------------------------------------------------------------

def test_works_on_tuples():
    arr = (10, 20, 30, 40, 50)
    assert search_leftmost_not_less_than(arr, 30) == 2
    assert search_leftmost_not_less_than(arr, 25) == 2
    assert search_leftmost_not_less_than(arr, 100) == 5


def test_works_on_strings():
    # Strings sort lexicographically, so this is a valid use case.
    arr = ["apple", "banana", "cherry", "date"]
    assert search_leftmost_not_less_than(arr, "banana") == 1
    assert search_leftmost_not_less_than(arr, "blueberry") == 2
    assert search_leftmost_not_less_than(arr, "aardvark") == 0
    assert search_leftmost_not_less_than(arr, "zebra") == 4


# ---------------------------------------------------------------------------
# Property-based sanity checks against the obvious brute force
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "arr,target,expected",
    [
        ([], 0, 0),
        ([1], 0, 0),
        ([1], 1, 0),
        ([1], 2, 1),
        ([1, 2, 3], 0, 0),
        ([1, 2, 3], 1, 0),
        ([1, 2, 3], 2, 1),
        ([1, 2, 3], 3, 2),
        ([1, 2, 3], 4, 3),
        ([-5, -3, -1, 0, 2, 4, 6], -4, 1),
        ([-5, -3, -1, 0, 2, 4, 6], 0, 3),
        ([-5, -3, -1, 0, 2, 4, 6], 1, 4),
        ([-5, -3, -1, 0, 2, 4, 6], 6, 6),
        ([-5, -3, -1, 0, 2, 4, 6], 7, 7),
        ([0, 0, 0, 1, 1, 1, 2, 2, 2], 0, 0),
        ([0, 0, 0, 1, 1, 1, 2, 2, 2], 1, 3),
        ([0, 0, 0, 1, 1, 1, 2, 2, 2], 2, 6),
        ([0, 0, 0, 1, 1, 1, 2, 2, 2], 3, 9),
    ],
)
def test_matches_brute_force_lower_bound(arr, target, expected):
    """Compare the implementation against a straightforward linear scan."""
    # Brute force reference: first index with arr[i] >= target, or len(arr).
    brute = next((i for i, v in enumerate(arr) if v >= target), len(arr))
    assert search_leftmost_not_less_than(arr, target) == brute
    # Also assert the explicit expectation, in case brute-force and impl
    # share the same bug.
    assert search_leftmost_not_less_than(arr, target) == expected


def test_returned_index_is_a_valid_lower_bound():
    """The returned index must satisfy the lower-bound contract for any
    sorted input."""
    arr = list(range(-10, 11, 2))  # [-10, -8, ..., 8, 10]
    for target in range(-12, 13):
        i = search_leftmost_not_less_than(arr, target)
        # Index must be in [0, len(arr)].
        assert 0 <= i <= len(arr)
        # Every element before i is strictly less than target.
        for v in arr[:i]:
            assert v < target
        # If i is a real index, the element at i must be >= target.
        if i < len(arr):
            assert arr[i] >= target