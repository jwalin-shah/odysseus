"""Tests for :mod:`search_sort.inversion_counter`."""

import pytest

from search_sort.inversion_counter import (
    count_inversions,
    count_inversions_inplace,
)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_list_has_zero_inversions():
    assert count_inversions([]) == 0


def test_single_element_has_zero_inversions():
    assert count_inversions([42]) == 0


def test_none_treated_like_empty():
    # The public function should be tolerant of ``None`` rather than
    # raising.  This mirrors the behaviour of len() based algorithms.
    assert count_inversions(None) == 0


# ---------------------------------------------------------------------------
# Tiny / known cases
# ---------------------------------------------------------------------------

def test_two_sorted_elements():
    assert count_inversions([1, 2]) == 0


def test_two_unsorted_elements():
    assert count_inversions([2, 1]) == 1


def test_three_with_one_inversion():
    # Inversions: (3, 2) only.
    assert count_inversions([1, 3, 2]) == 1


def test_three_reverse_sorted():
    # Inversions: (3,2), (3,1), (2,1).
    assert count_inversions([3, 2, 1]) == 3


# ---------------------------------------------------------------------------
# Larger, well-known cases
# ---------------------------------------------------------------------------

def test_already_sorted_array():
    assert count_inversions([1, 2, 3, 4, 5, 6, 7, 8]) == 0


def test_reverse_sorted_array():
    # n = 8 -> n*(n-1)/2 = 28.
    assert count_inversions([8, 7, 6, 5, 4, 3, 2, 1]) == 28


def test_random_array_matches_naive_count():
    arr = [2, 4, 1, 3, 5]
    # Inversions: (2,1), (4,1), (4,3) -> 3.
    assert count_inversions(arr) == 3


def test_larger_random_array_matches_naive_count():
    arr = [5, 3, 8, 1, 9, 2, 7, 4, 6]
    expected = _naive_count(arr)
    assert count_inversions(arr) == expected


# ---------------------------------------------------------------------------
# Duplicates and mixed signs
# ---------------------------------------------------------------------------

def test_array_of_duplicates_has_zero_inversions():
    assert count_inversions([1, 1, 1, 1, 1]) == 0


def test_array_with_duplicates():
    # Inversions: (3,1), (3,2), (3,1), (2,1)
    assert count_inversions([3, 1, 2, 1]) == 4


def test_array_with_negatives():
    # Inversions: (-1, -2) only.
    assert count_inversions([-1, -2, 0, 1, 2]) == 1


def test_array_with_mixed_signs_matches_naive_count():
    arr = [-3, 5, -1, 0, 4, -2, 2]
    assert count_inversions(arr) == _naive_count(arr)


# ---------------------------------------------------------------------------
# Non-mutation guarantee / tuple input
# ---------------------------------------------------------------------------

def test_does_not_modify_input_list():
    arr = [3, 1, 4, 1, 5, 9, 2, 6]
    snapshot = list(arr)
    count_inversions(arr)
    assert arr == snapshot


def test_accepts_tuple_input():
    assert count_inversions((3, 1, 2)) == 2


def test_invalid_input_raises_type_error():
    with pytest.raises(TypeError):
        count_inversions(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# In-place variant
# ---------------------------------------------------------------------------

def test_inplace_variant_sorts_and_counts():
    arr = [5, 4, 3, 2, 1]
    inv = count_inversions_inplace(arr)
    assert inv == 10
    assert arr == [1, 2, 3, 4, 5]


def test_inplace_variant_matches_functional_count():
    arr = [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
    assert count_inversions_inplace(arr) == _naive_count([9, 8, 7, 6, 5, 4, 3, 2, 1, 0])


# ---------------------------------------------------------------------------
# Helper used by the larger test cases
# ---------------------------------------------------------------------------

def _naive_count(arr):
    """O(n^2) reference implementation used as an oracle in tests."""
    n = len(arr)
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            if arr[i] > arr[j]:
                count += 1
    return count