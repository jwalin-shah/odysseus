"""Tests for ``solutions.select_kth``."""

import pytest

from solutions.select_kth import select_kth


class TestBasicBehaviour:
    """Core correctness of select_kth on small inputs."""

    def test_minimum_is_first_element(self):
        assert select_kth([3, 1, 4, 1, 5, 9, 2, 6], 0) == 1

    def test_maximum_is_last_element(self):
        assert select_kth([3, 1, 4, 1, 5, 9, 2, 6], 7) == 9

    def test_median_of_even_length_list(self):
        # Sorted: [1, 1, 2, 3, 4, 5, 6, 9] -> index 4 is 4
        assert select_kth([3, 1, 4, 1, 5, 9, 2, 6], 4) == 4

    def test_two_elements_returns_min(self):
        assert select_kth([2, 1], 0) == 1

    def test_two_elements_returns_max(self):
        assert select_kth([2, 1], 1) == 2

    def test_single_element_list(self):
        assert select_kth([42], 0) == 42


class TestFullSortAgreement:
    """select_kth should agree with ``sorted`` for every index."""

    def test_matches_sorted_for_random_list(self):
        arr = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9]
        expected = sorted(arr)
        for k in range(len(arr)):
            assert select_kth(arr, k) == expected[k]

    def test_matches_sorted_for_already_sorted(self):
        arr = list(range(20))
        for k in range(len(arr)):
            assert select_kth(arr, k) == k

    def test_matches_sorted_for_reverse_sorted(self):
        arr = list(range(20, 0, -1))
        for k in range(len(arr)):
            assert select_kth(arr, k) == k + 1

    def test_all_equal_elements(self):
        arr = [7, 7, 7, 7, 7, 7, 7]
        for k in range(len(arr)):
            assert select_kth(arr, k) == 7

    def test_floats_match_sorted(self):
        arr = [3.5, 1.2, 4.7, 1.1, 5.0, 9.9, 2.3, 6.6]
        expected = sorted(arr)
        for k in range(len(arr)):
            assert select_kth(arr, k) == pytest.approx(expected[k])

    def test_strings_match_sorted(self):
        arr = ["banana", "apple", "cherry", "date"]
        for k in range(len(arr)):
            assert select_kth(arr, k) == sorted(arr)[k]


class TestErrorHandling:
    """Edge cases and error conditions."""

    def test_empty_sequence_raises(self):
        with pytest.raises(IndexError):
            select_kth([], 0)

    def test_negative_k_raises(self):
        with pytest.raises(IndexError):
            select_kth([1, 2, 3], -1)

    def test_k_equal_to_length_raises(self):
        with pytest.raises(IndexError):
            select_kth([1, 2, 3], 3)

    def test_k_way_out_of_bounds_raises(self):
        with pytest.raises(IndexError):
            select_kth([1, 2, 3], 100)

    def test_non_integer_k_raises(self):
        with pytest.raises(TypeError):
            select_kth([1, 2, 3], 1.0)  # type: ignore[arg-type]


class TestImmutability:
    """The function must not mutate the caller's sequence."""

    def test_input_list_unchanged(self):
        arr = [3, 1, 4, 1, 5, 9, 2, 6]
        snapshot = list(arr)
        for k in range(len(arr)):
            select_kth(arr, k)
        assert arr == snapshot

    def test_input_tuple_usable_repeatedly(self):
        arr = (5, 2, 8, 1, 9, 3)
        # Calling on a tuple should not raise; results should be stable.
        first = [select_kth(arr, k) for k in range(len(arr))]
        second = [select_kth(arr, k) for k in range(len(arr))]
        assert first == second == sorted(arr)