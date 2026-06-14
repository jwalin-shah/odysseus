"""Tests for :mod:`search_ops.exponential_search`."""

import pytest

from search_ops.exponential_search import exponential_search


# ---------------------------------------------------------------------------
# Edge cases - empty and tiny inputs
# ---------------------------------------------------------------------------


def test_empty_array_returns_minus_one():
    assert exponential_search([], 1) == -1


def test_single_element_array_found():
    assert exponential_search([42], 42) == 0


def test_single_element_array_not_found_below():
    assert exponential_search([42], 10) == -1


def test_single_element_array_not_found_above():
    assert exponential_search([42], 100) == -1


def test_two_elements_first_match():
    assert exponential_search([1, 2], 1) == 0


def test_two_elements_second_match():
    assert exponential_search([1, 2], 2) == 1


def test_two_elements_no_match_below():
    assert exponential_search([1, 2], 0) == -1


def test_two_elements_no_match_above():
    assert exponential_search([1, 2], 3) == -1


# ---------------------------------------------------------------------------
# Standard positive cases
# ---------------------------------------------------------------------------


def test_target_at_first_position():
    arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert exponential_search(arr, 1) == 0


def test_target_at_last_position():
    arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert exponential_search(arr, 10) == 9


def test_target_in_middle_of_small_array():
    arr = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert exponential_search(arr, 60) == 5


def test_target_in_middle_of_medium_array():
    arr = list(range(0, 100, 2))  # [0, 2, 4, ..., 98]
    assert exponential_search(arr, 50) == 25
    assert exponential_search(arr, 0) == 0
    assert exponential_search(arr, 98) == 49


# ---------------------------------------------------------------------------
# Negative cases - target not present
# ---------------------------------------------------------------------------


def test_target_not_in_array_above_max():
    arr = [1, 2, 3, 4, 5]
    assert exponential_search(arr, 6) == -1


def test_target_not_in_array_below_min():
    arr = [1, 2, 3, 4, 5]
    assert exponential_search(arr, 0) == -1


def test_target_not_in_array_within_range():
    arr = [1, 3, 5, 7, 9, 11, 13, 15]
    assert exponential_search(arr, 4) == -1
    assert exponential_search(arr, 8) == -1
    assert exponential_search(arr, 14) == -1


def test_all_identical_elements_target_matches():
    # All elements equal the target - any index is a valid answer.
    arr = [7, 7, 7, 7, 7]
    result = exponential_search(arr, 7)
    assert 0 <= result < len(arr)
    assert arr[result] == 7


def test_all_identical_elements_target_misses():
    arr = [7, 7, 7, 7, 7]
    assert exponential_search(arr, 8) == -1


def test_duplicates_returns_a_valid_index_of_target():
    # Exponential search on duplicates is allowed to return *any* matching
    # index, so we just verify the returned slot actually contains the
    # target value.
    arr = [1, 2, 2, 2, 3, 4, 5]
    result = exponential_search(arr, 2)
    assert result in (1, 2, 3)
    assert arr[result] == 2


# ---------------------------------------------------------------------------
# Larger / non-integer arrays
# ---------------------------------------------------------------------------


def test_large_sorted_array_extremes():
    arr = list(range(1000))
    assert exponential_search(arr, 0) == 0
    assert exponential_search(arr, 999) == 999
    assert exponential_search(arr, 1000) == -1
    assert exponential_search(arr, -1) == -1


def test_large_sorted_array_middle():
    arr = list(range(1000))
    assert exponential_search(arr, 500) == 500
    assert exponential_search(arr, 499) == 499
    assert exponential_search(arr, 501) == 501


def test_string_array():
    arr = ["apple", "banana", "cherry", "date", "elderberry", "fig"]
    assert exponential_search(arr, "apple") == 0
    assert exponential_search(arr, "cherry") == 2
    assert exponential_search(arr, "fig") == 5
    assert exponential_search(arr, "grape") == -1
    assert exponential_search(arr, "aardvark") == -1


def test_float_array():
    arr = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
    assert exponential_search(arr, 0.3) == 2
    assert exponential_search(arr, 1.0) == 9
    assert exponential_search(arr, 0.15) == -1
    assert exponential_search(arr, 1.5) == -1


def test_negative_numbers():
    arr = [-100, -50, -10, -5, 0, 5, 10, 50, 100]
    assert exponential_search(arr, -100) == 0
    assert exponential_search(arr, 0) == 4
    assert exponential_search(arr, 100) == 8
    assert exponential_search(arr, -25) == -1
    assert exponential_search(arr, 25) == -1


# ---------------------------------------------------------------------------
# Algorithmic property tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "arr, target, expected",
    [
        ([1, 2, 3, 4, 5], 1, 0),
        ([1, 2, 3, 4, 5], 2, 1),
        ([1, 2, 3, 4, 5], 3, 2),
        ([1, 2, 3, 4, 5], 4, 3),
        ([1, 2, 3, 4, 5], 5, 4),
        ([1, 2, 3, 4, 5], 0, -1),
        ([1, 2, 3, 4, 5], 6, -1),
        (list(range(20)), 7, 7),
        (list(range(20)), 19, 19),
        (list(range(20)), 20, -1),
    ],
)
def test_parametrized_search(arr, target, expected):
    assert exponential_search(arr, target) == expected


def test_agrees_with_binary_search_on_random_inputs():
    """Cross-check the result against a naive linear search."""
    import random

    random.seed(0xC0FFEE)
    for _ in range(50):
        size = random.randint(0, 200)
        arr = sorted(random.sample(range(-500, 500), k=min(size, 1000 - size)))
        # The set of available integers is large, so duplicates are rare
        # - this is fine because the function is also defined for
        # duplicates, and ``in`` semantics match linear search here.
        for target in (arr[0], arr[-1], 9999, -9999) if arr else (9999,):
            try:
                expected = arr.index(target)
            except ValueError:
                expected = -1
            assert exponential_search(arr, target) == expected