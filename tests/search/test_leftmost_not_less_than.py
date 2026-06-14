"""Tests for ``search.leftmost_not_less_than``."""

import pytest

from search.leftmost_not_less_than import leftmost_not_less_than


# ---------------------------------------------------------------------------
# Basic correctness on a typical sorted array
# ---------------------------------------------------------------------------

def test_target_present_in_middle():
    arr = [1, 3, 5, 7, 9, 11, 13]
    assert leftmost_not_less_than(arr, 7) == 3


def test_target_present_at_first_position():
    arr = [1, 3, 5, 7, 9, 11, 13]
    assert leftmost_not_less_than(arr, 1) == 0


def test_target_present_at_last_position():
    arr = [1, 3, 5, 7, 9, 11, 13]
    assert leftmost_not_less_than(arr, 13) == 6


# ---------------------------------------------------------------------------
# Target is not in the array
# ---------------------------------------------------------------------------

def test_target_smaller_than_every_element():
    arr = [2, 4, 6, 8, 10]
    # Smallest value >= -5 is 2 at index 0
    assert leftmost_not_less_than(arr, -5) == 0


def test_target_larger_than_every_element():
    arr = [2, 4, 6, 8, 10]
    # No element is >= 100, so we return the insertion point
    assert leftmost_not_less_than(arr, 100) == len(arr)


def test_target_between_two_elements_lower_side():
    arr = [1, 2, 4, 5, 6]
    # 3 is missing; the first element >= 3 is 4 at index 2
    assert leftmost_not_less_than(arr, 3) == 2


def test_target_between_two_elements_upper_side():
    arr = [1, 2, 4, 5, 6]
    # 4 < 4.5 < 5: first element >= 4.5 is 5 at index 3
    assert leftmost_not_less_than(arr, 4.5) == 3


# ---------------------------------------------------------------------------
# Edge cases: empty array and single-element arrays
# ---------------------------------------------------------------------------

def test_empty_array_returns_zero():
    # With no elements the only valid insertion point is 0.
    assert leftmost_not_less_than([], 0) == 0
    assert leftmost_not_less_than([], -100) == 0
    assert leftmost_not_less_than([], 100) == 0


def test_single_element_target_smaller():
    assert leftmost_not_less_than([5], 3) == 0


def test_single_element_target_larger():
    assert leftmost_not_less_than([5], 10) == 1


def test_single_element_target_equal():
    assert leftmost_not_less_than([5], 5) == 0


# ---------------------------------------------------------------------------
# Duplicates: the LEFTMOST occurrence must be returned
# ---------------------------------------------------------------------------

def test_duplicates_returns_leftmost_occurrence():
    arr = [1, 2, 2, 2, 2, 3, 4, 5]
    # Multiple 2s exist; the leftmost 2 is at index 1.
    assert leftmost_not_less_than(arr, 2) == 1


def test_duplicates_at_start():
    arr = [3, 3, 3, 3, 5, 7]
    assert leftmost_not_less_than(arr, 3) == 0


def test_duplicates_at_end():
    arr = [1, 2, 4, 5, 5, 5, 5]
    assert leftmost_not_less_than(arr, 5) == 3


def test_all_elements_equal():
    arr = [4, 4, 4, 4, 4]
    assert leftmost_not_less_than(arr, 4) == 0
    assert leftmost_not_less_than(arr, 3) == 0
    assert leftmost_not_less_than(arr, 5) == 5


# ---------------------------------------------------------------------------
# Negative numbers, floats, and other comparable types
# ---------------------------------------------------------------------------

def test_negative_numbers():
    arr = [-10, -7, -3, 0, 2, 4]
    assert leftmost_not_less_than(arr, -8) == 1
    assert leftmost_not_less_than(arr, -3) == 2
    assert leftmost_not_less_than(arr, -4) == 2
    assert leftmost_not_less_than(arr, 1) == 4


def test_floats_sorted():
    arr = [0.1, 0.2, 0.3, 0.4, 0.5]
    assert leftmost_not_less_than(arr, 0.25) == 2
    assert leftmost_not_less_than(arr, 0.3) == 2
    assert leftmost_not_less_than(arr, 0.31) == 3


# ---------------------------------------------------------------------------
# Large / odd-sized arrays to exercise the binary search loop
# ---------------------------------------------------------------------------

def test_large_array_exact_hit():
    arr = list(range(-1000, 1000, 2))  # -1000, -998, ..., 998
    # arr[500] = 0
    assert leftmost_not_less_than(arr, 0) == 500
    # arr[0]  = -1000
    assert leftmost_not_less_than(arr, -1000) == 0
    # arr[-1] = 998
    assert leftmost_not_less_than(arr, 998) == 999


def test_large_array_miss():
    arr = list(range(-1000, 1000, 2))
    # 1 is odd -> not in arr; first element >= 1 is 2 at index 501
    assert leftmost_not_less_than(arr, 1) == 501
    # 999 is odd -> not in arr; insertion point is len(arr)
    assert leftmost_not_less_than(arr, 999) == len(arr)


# ---------------------------------------------------------------------------
# Result must be a valid insertion index
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "arr, target, expected",
    [
        ([], 5, 0),
        ([1], 1, 0),
        ([1], 2, 1),
        ([1, 2, 3, 4, 5], 0, 0),
        ([1, 2, 3, 4, 5], 3, 2),
        ([1, 2, 3, 4, 5], 6, 5),
        ([1, 3, 5, 7, 9], 4, 2),
        ([1, 2, 2, 2, 3, 4], 2, 1),
        ([-5, -5, -2, 0, 1, 1, 3], -5, 0),
        ([-5, -5, -2, 0, 1, 1, 3], -3, 2),
        ([-5, -5, -2, 0, 1, 1, 3], 1, 4),
        ([-5, -5, -2, 0, 1, 1, 3], 4, 7),
    ],
)
def test_parametrized_cases(arr, target, expected):
    result = leftmost_not_less_than(arr, target)
    # Result must be a valid index in [0, len(arr)].
    assert 0 <= result <= len(arr)
    # If there is an element >= target, the element at `result` must satisfy
    # the condition; if not, the result must be len(arr) (insertion point).
    if result < len(arr):
        assert arr[result] >= target
        # And it must be the LEFTMOST such index.
        if result > 0:
            assert arr[result - 1] < target
    else:
        # All elements (if any) are < target.
        assert all(x < target for x in arr)
    assert result == expected