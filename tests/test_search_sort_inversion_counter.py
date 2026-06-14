import pytest
from src.search_sort_inversion_counter import search_sort_inversion_counter


def test_empty_iterable():
    assert search_sort_inversion_counter([]) == 0


def test_single_element():
    assert search_sort_inversion_counter([1]) == 0


def test_two_elements_sorted():
    assert search_sort_inversion_counter([1, 2]) == 0


def test_two_elements_inverted():
    assert search_sort_inversion_counter([2, 1]) == 1


def test_sorted_list_no_inversions():
    assert search_sort_inversion_counter([1, 2, 3, 4, 5]) == 0


def test_reverse_sorted_max_inversions():
    # n*(n-1)/2 = 5*4/2 = 10
    assert search_sort_inversion_counter([5, 4, 3, 2, 1]) == 10


def test_basic_inversions():
    # [4,2,3,1]: pairs (4,2),(4,3),(4,1),(2,1),(3,1) = 5
    assert search_sort_inversion_counter([4, 2, 3, 1]) == 5


def test_duplicates_are_not_inversions():
    # Equal elements do not count as inversions
    assert search_sort_inversion_counter([1, 1, 1, 1]) == 0
    # [2,1,2,1]: (2,1)@0-1, (2,1)@0-3, (2,1)@2-3 = 3
    assert search_sort_inversion_counter([2, 1, 2, 1]) == 3


def test_with_negative_numbers():
    assert search_sort_inversion_counter([-1, -2, -3]) == 3


def test_accepts_arbitrary_iterables():
    # Generator expression
    assert search_sort_inversion_counter(x for x in [4, 2, 3, 1]) == 5
    # Tuple
    assert search_sort_inversion_counter((4, 2, 3, 1)) == 5
    # range
    assert search_sort_inversion_counter(range(5, 0, -1)) == 10
    # Empty generator
    assert search_sort_inversion_counter(x for x in []) == 0


def test_large_input_correctness():
    # Brute-force comparison for a small random list
    data = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
    expected = sum(
        1 for i in range(len(data)) for j in range(i + 1, len(data)) if data[i] > data[j]
    )
    assert search_sort_inversion_counter(data) == expected