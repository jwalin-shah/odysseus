"""Tests for ``solutions_select_kth``."""
from __future__ import annotations

import os
import random
import sys

import pytest

# Make ``src/`` importable regardless of how pytest is invoked.
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "..", "src"))

from solutions_select_kth import solutions_select_kth  # noqa: E402


class TestBasics:
    def test_smallest_element(self):
        assert solutions_select_kth([5, 2, 8, 1, 9, 3], 0) == 1

    def test_largest_element(self):
        assert solutions_select_kth([5, 2, 8, 1, 9, 3], 5) == 9

    def test_middle_element(self):
        # Sorted order: [1, 2, 3, 5, 8, 9]; index 3 -> 5.
        assert solutions_select_kth([5, 2, 8, 1, 9, 3], 3) == 5

    def test_returns_value_from_list_with_one_element(self):
        assert solutions_select_kth([42], 0) == 42

    def test_two_elements_in_order(self):
        assert solutions_select_kth([1, 2], 0) == 1
        assert solutions_select_kth([1, 2], 1) == 2

    def test_two_elements_reversed(self):
        assert solutions_select_kth([2, 1], 0) == 1
        assert solutions_select_kth([2, 1], 1) == 2


class TestProperties:
    def test_matches_sorted_for_random_input(self):
        rng = random.Random(0xC0FFEE)
        for _ in range(100):
            arr = [rng.randint(-50, 50) for _ in range(rng.randint(1, 40))]
            expected = sorted(arr)
            for k in range(len(arr)):
                assert solutions_select_kth(arr, k) == expected[k]

    def test_does_not_mutate_input_list(self):
        arr = [5, 2, 8, 1, 9, 3]
        snapshot = arr.copy()
        solutions_select_kth(arr, 0)
        solutions_select_kth(arr, 5)
        assert arr == snapshot

    def test_handles_duplicates(self):
        arr = [3, 1, 3, 2, 3, 1, 2, 3]
        expected = sorted(arr)
        for k in range(len(arr)):
            assert solutions_select_kth(arr, k) == expected[k]

    def test_handles_all_equal_elements(self):
        arr = [7] * 10
        for k in range(len(arr)):
            assert solutions_select_kth(arr, k) == 7

    def test_handles_negative_numbers(self):
        arr = [-5, 3, -1, 0, 7, -8, 2]
        expected = sorted(arr)
        for k in range(len(arr)):
            assert solutions_select_kth(arr, k) == expected[k]

    def test_handles_floats(self):
        arr = [2.5, 0.1, 1.5, 0.1, 2.5, -1.0]
        expected = sorted(arr)
        for k in range(len(arr)):
            assert solutions_select_kth(arr, k) == expected[k]

    def test_accepts_tuple(self):
        assert solutions_select_kth((3, 1, 2), 0) == 1
        assert solutions_select_kth((3, 1, 2), 1) == 2
        assert solutions_select_kth((3, 1, 2), 2) == 3

    def test_accepts_strings(self):
        arr = ["banana", "apple", "cherry", "date"]
        expected = sorted(arr)
        for k in range(len(arr)):
            assert solutions_select_kth(arr, k) == expected[k]

    def test_already_sorted_input(self):
        arr = list(range(20))
        for k in range(len(arr)):
            assert solutions_select_kth(arr, k) == k

    def test_reverse_sorted_input(self):
        arr = list(range(20, 0, -1))
        for k in range(len(arr)):
            assert solutions_select_kth(arr, k) == k + 1


class TestErrors:
    def test_empty_sequence_raises_value_error(self):
        with pytest.raises(ValueError):
            solutions_select_kth([], 0)

    def test_negative_k_raises_index_error(self):
        with pytest.raises(IndexError):
            solutions_select_kth([1, 2, 3], -1)

    def test_k_equal_to_length_raises_index_error(self):
        with pytest.raises(IndexError):
            solutions_select_kth([1, 2, 3], 3)

    def test_k_way_too_large_raises_index_error(self):
        with pytest.raises(IndexError):
            solutions_select_kth([1, 2, 3], 99)


class TestScaling:
    def test_large_array(self):
        rng = random.Random(123)
        arr = [rng.randint(0, 10_000) for _ in range(2_000)]
        expected = sorted(arr)
        # Spot-check several positions rather than every index to keep the
        # test fast while still exercising the algorithm at scale.
        for k in (0, 1, 50, 500, 1_000, 1_999):
            assert solutions_select_kth(arr, k) == expected[k]