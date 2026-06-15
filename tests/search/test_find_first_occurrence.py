"""Tests for search.find_first_occurrence."""

import pytest

from search.find_first_occurrence import find_first_occurrence


def test_target_present_single_occurrence():
    # Basic case: target appears exactly once in the middle of the list.
    arr = [1, 3, 5, 7, 9, 11]
    assert find_first_occurrence(arr, 7) == 3


def test_target_present_multiple_occurrences_returns_first():
    # When the target appears multiple times, return the *first* index.
    arr = [1, 2, 2, 2, 3, 4, 5]
    assert find_first_occurrence(arr, 2) == 1


def test_target_absent_returns_negative_one():
    # Target smaller than the minimum element.
    assert find_first_occurrence([2, 4, 6, 8], 1) == -1
    # Target larger than the maximum element.
    assert find_first_occurrence([2, 4, 6, 8], 10) == -1
    # Target between two elements (would not exist even in a non-sorted list).
    assert find_first_occurrence([1, 3, 5, 7, 9], 4) == -1


def test_empty_list_returns_negative_one():
    assert find_first_occurrence([], 5) == -1


def test_single_element_list_match():
    assert find_first_occurrence([42], 42) == 0


def test_single_element_list_no_match():
    assert find_first_occurrence([42], 7) == -1


def test_target_at_first_position():
    arr = [1, 2, 3, 4, 5]
    assert find_first_occurrence(arr, 1) == 0


def test_target_at_last_position():
    arr = [1, 2, 3, 4, 5]
    assert find_first_occurrence(arr, 5) == 4


def test_all_duplicates_match_first_index():
    arr = [4, 4, 4, 4, 4]
    assert find_first_occurrence(arr, 4) == 0


def test_all_duplicates_no_match():
    arr = [4, 4, 4, 4, 4]
    assert find_first_occurrence(arr, 5) == -1


def test_negative_numbers():
    arr = [-10, -5, -3, -1, 0, 2, 4]
    assert find_first_occurrence(arr, -5) == 1
    assert find_first_occurrence(arr, -3) == 2
    assert find_first_occurrence(arr, 0) == 4


def test_duplicate_block_at_start():
    arr = [2, 2, 2, 3, 4, 5]
    assert find_first_occurrence(arr, 2) == 0


def test_duplicate_block_in_middle():
    arr = [1, 2, 3, 3, 3, 4, 5]
    assert find_first_occurrence(arr, 3) == 2


def test_duplicate_block_at_end():
    arr = [1, 2, 3, 4, 5, 5, 5]
    assert find_first_occurrence(arr, 5) == 4


def test_target_smaller_than_all_elements():
    arr = [10, 20, 30, 40, 50]
    assert find_first_occurrence(arr, 0) == -1


def test_target_larger_than_all_elements():
    arr = [10, 20, 30, 40, 50]
    assert find_first_occurrence(arr, 100) == -1


def test_two_element_list_match_first():
    assert find_first_occurrence([1, 2], 1) == 0


def test_two_element_list_match_second():
    assert find_first_occurrence([1, 2], 2) == 1


def test_two_element_list_no_match():
    assert find_first_occurrence([1, 2], 3) == -1


def test_large_sorted_list_binary_search_correctness():
    # 0..49, then 50 ten times, then 51..99 -> 50 first appears at 50, 99 first
    # appears at 50 + 10 + 48 = 108, 100 is absent.
    arr = list(range(50)) + [50] * 10 + list(range(51, 100))
    assert find_first_occurrence(arr, 50) == 50
    assert find_first_occurrence(arr, 0) == 0
    assert find_first_occurrence(arr, 49) == 49
    assert find_first_occurrence(arr, 99) == 108
    assert find_first_occurrence(arr, 100) == -1
    # Sanity: total length is 50 + 10 + 49 = 109, so a valid last index is 108.
    assert len(arr) == 109


@pytest.mark.parametrize(
    "arr,target,expected",
    [
        ([], 1, -1),
        ([1], 1, 0),
        ([1], 2, -1),
        ([1, 1, 1], 1, 0),
        ([1, 2, 3, 4, 5], 3, 2),
        ([1, 2, 3, 4, 5], 1, 0),
        ([1, 2, 3, 4, 5], 5, 4),
        ([1, 2, 3, 4, 5], 6, -1),
        ([1, 2, 2, 2, 3], 2, 1),
        ([1, 2, 2, 2, 3], 3, 4),
        ([-5, -3, -1, 0, 2, 4], -1, 2),
        ([-5, -3, -1, 0, 2, 4], -6, -1),
    ],
)
def test_parametrized_cases(arr, target, expected):
    assert find_first_occurrence(arr, target) == expected
