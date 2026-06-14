"""Pytest suite for :mod:`interp_search`."""

import os
import sys

# Make the project root importable regardless of how pytest is invoked.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from interp_search import interp_search  # noqa: E402


# ---------------------------------------------------------------------------
# Basic functionality
# ---------------------------------------------------------------------------


def test_finds_elements_in_uniform_array():
    arr = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    assert interp_search(arr, 10) == 0
    assert interp_search(arr, 30) == 2
    assert interp_search(arr, 50) == 4
    assert interp_search(arr, 70) == 6
    assert interp_search(arr, 90) == 8


def test_returns_minus_one_when_key_absent():
    arr = [10, 20, 30, 40, 50, 60, 70, 80, 90]
    assert interp_search(arr, 5) == -1        # below range
    assert interp_search(arr, 100) == -1      # above range
    assert interp_search(arr, 35) == -1       # in range, missing
    assert interp_search(arr, -1000) == -1    # far below


def test_empty_array_returns_minus_one():
    assert interp_search([], 5) == -1


def test_single_element_array():
    assert interp_search([42], 42) == 0
    assert interp_search([42], 41) == -1
    assert interp_search([42], 43) == -1


def test_finds_first_and_last_elements():
    arr = list(range(0, 1000, 7))  # sorted, non-trivial spread
    first = arr[0]
    last = arr[-1]
    assert interp_search(arr, first) == 0
    assert interp_search(arr, last) == len(arr) - 1


# ---------------------------------------------------------------------------
# Edge cases / robustness
# ---------------------------------------------------------------------------


def test_uniform_values_does_not_crash():
    """Arrays with identical values must not trigger a division by zero."""
    arr = [5, 5, 5, 5, 5]
    # If the key matches, the implementation must find *some* index.
    result = interp_search(arr, 5)
    assert result != -1
    assert arr[result] == 5
    # A key that is not present must be reported as missing.
    assert interp_search(arr, 3) == -1


def test_floats_are_supported():
    arr = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]
    assert interp_search(arr, 0.1) == 0
    assert interp_search(arr, 0.6) == 5
    assert interp_search(arr, 0.35) == -1
    assert interp_search(arr, 0.4) == 3


def test_duplicates_returns_an_index_of_key():
    arr = [1, 2, 2, 2, 3, 4, 5]
    idx = interp_search(arr, 2)
    assert idx != -1
    assert arr[idx] == 2


def test_large_uniform_distribution():
    arr = list(range(0, 10001))  # 0..10000 inclusive
    assert interp_search(arr, 0) == 0
    assert interp_search(arr, 10000) == 10000
    assert interp_search(arr, 4321) == 4321
    assert interp_search(arr, 10001) == -1
    assert interp_search(arr, -1) == -1


def test_negative_values():
    arr = [-50, -30, -10, 0, 10, 20, 30]
    assert interp_search(arr, -50) == 0
    assert interp_search(arr, -30) == 1
    assert interp_search(arr, 0) == 3
    assert interp_search(arr, 30) == 6
    assert interp_search(arr, -5) == -1


def test_two_element_array():
    assert interp_search([1, 2], 1) == 0
    assert interp_search([1, 2], 2) == 1
    assert interp_search([1, 2], 0) == -1
    assert interp_search([1, 2], 3) == -1


def test_accepts_arbitrary_indexable():
    """The implementation should work with tuples and other indexables too."""
    tup = (1, 3, 5, 7, 9)
    assert interp_search(tup, 5) == 2
    assert interp_search(tup, 4) == -1