"""Tests for ``src.search_peak_finder.search_peak_finder``."""

import os
import sys

import pytest

# Make ``src`` importable when pytest is invoked from the project root.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.search_peak_finder import search_peak_finder


def _is_peak(arr, idx):
    """Return True iff ``arr[idx]`` satisfies the peak condition."""
    n = len(arr)
    if idx < 0 or idx >= n:
        return False
    if idx == 0:
        return arr[idx] >= arr[1]
    if idx == n - 1:
        return arr[idx] >= arr[n - 2]
    return arr[idx] >= arr[idx - 1] and arr[idx] >= arr[idx + 1]


def test_empty_array_returns_none():
    assert search_peak_finder([]) is None


def test_single_element():
    assert search_peak_finder([42]) == 0


def test_first_element_is_peak():
    # Descending array: the first element is the peak.
    arr = [10, 8, 6, 4, 2, 0]
    idx = search_peak_finder(arr)
    assert idx == 0
    assert _is_peak(arr, idx)


def test_last_element_is_peak():
    # Ascending array: the last element is the peak.
    arr = [0, 2, 4, 6, 8, 10]
    idx = search_peak_finder(arr)
    assert idx == len(arr) - 1
    assert _is_peak(arr, idx)


def test_two_elements_first_is_peak():
    arr = [5, 1]
    assert search_peak_finder(arr) == 0


def test_two_elements_last_is_peak():
    arr = [1, 5]
    assert search_peak_finder(arr) == 1


def test_peak_in_middle():
    arr = [1, 3, 5, 4, 2]
    idx = search_peak_finder(arr)
    assert idx == 2
    assert _is_peak(arr, idx)


def test_peak_in_middle_descending_then_ascending():
    # A "valley" with two peaks; either is acceptable, both must be valid.
    arr = [5, 4, 3, 2, 1, 2, 3, 4, 5]
    idx = search_peak_finder(arr)
    assert idx is not None
    assert _is_peak(arr, idx)
    # The global maximum (5) is a valid peak; accept either end.
    assert arr[idx] in (5,)


def test_multiple_peaks_finds_one():
    arr = [1, 5, 1, 3, 1, 4, 1]
    idx = search_peak_finder(arr)
    assert idx is not None
    assert _is_peak(arr, idx)
    # The first peak is a valid answer and the binary search will
    # return one of {1, 3, 5}.
    assert idx in (1, 3, 5)


def test_all_equal_elements():
    arr = [7, 7, 7, 7, 7]
    idx = search_peak_finder(arr)
    assert idx is not None
    assert _is_peak(arr, idx)
    # Any index is valid; the algorithm returns 0 for this case.
    assert idx == 0


def test_long_random_peak_is_valid():
    arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    idx = search_peak_finder(arr)
    assert idx is not None
    assert _is_peak(arr, idx)


def test_negative_values():
    arr = [-10, -5, -1, -3, -7, -12]
    idx = search_peak_finder(arr)
    assert idx is not None
    assert _is_peak(arr, idx)
    # -1 is the global maximum and a valid peak.
    assert arr[idx] == -1


def test_returns_index_type_int():
    arr = [3, 2, 1]
    result = search_peak_finder(arr)
    assert isinstance(result, int)


def test_does_not_mutate_input():
    arr = [1, 3, 2, 4, 1]
    snapshot = list(arr)
    search_peak_finder(arr)
    assert arr == snapshot