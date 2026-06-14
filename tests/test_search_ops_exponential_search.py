"""Pytest suite for ``search_ops_exponential_search.exponential_search``."""

import os
import sys

# Make the ``src`` directory importable regardless of how pytest is invoked.
_SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, os.path.abspath(_SRC))

from search_ops_exponential_search import exponential_search  # noqa: E402


class TestExponentialSearch:
    # --- trivial / boundary cases ---------------------------------------

    def test_empty_list_returns_minus_one(self):
        assert exponential_search([], 5) == -1

    def test_single_element_present(self):
        assert exponential_search([42], 42) == 0

    def test_single_element_absent(self):
        assert exponential_search([42], 7) == -1

    # --- position-based cases -------------------------------------------

    def test_target_at_first_position(self):
        assert exponential_search([1, 2, 3, 4, 5], 1) == 0

    def test_target_at_last_position(self):
        assert exponential_search([1, 2, 3, 4, 5], 5) == 4

    def test_target_in_middle(self):
        assert exponential_search([10, 20, 30, 40, 50, 60, 70], 40) == 3

    # --- out-of-range cases ---------------------------------------------

    def test_target_smaller_than_all_elements(self):
        assert exponential_search([10, 20, 30, 40], 5) == -1

    def test_target_larger_than_all_elements(self):
        assert exponential_search([1, 2, 3, 4], 99) == -1

    def test_target_between_two_elements(self):
        # Both neighbours exist, but the value itself does not.
        assert exponential_search([1, 3, 5, 7, 9], 4) == -1

    # --- duplicates -----------------------------------------------------

    def test_duplicates_returns_first_occurrence(self):
        arr = [1, 2, 2, 2, 2, 3, 4, 5]
        assert exponential_search(arr, 2) == 1

    # --- two-element arrays ---------------------------------------------

    def test_two_elements_first(self):
        assert exponential_search([1, 2], 1) == 0

    def test_two_elements_second(self):
        assert exponential_search([1, 2], 2) == 1

    # --- larger arrays ---------------------------------------------------

    def test_large_even_spaced_array(self):
        arr = list(range(0, 1000, 2))  # 0, 2, 4, ..., 998
        assert exponential_search(arr, 0) == 0
        assert exponential_search(arr, 500) == 250
        assert exponential_search(arr, 998) == 499
        assert exponential_search(arr, 999) == -1

    def test_large_odd_spaced_array(self):
        arr = list(range(-50, 51))  # -50 .. 50
        assert exponential_search(arr, -50) == 0
        assert exponential_search(arr, 0) == 50
        assert exponential_search(arr, 50) == 100
        assert exponential_search(arr, 51) == -1
        assert exponential_search(arr, -100) == -1

    # --- non-numeric payloads -------------------------------------------

    def test_strings_sorted_alphabetically(self):
        words = ["apple", "banana", "cherry", "date", "elderberry"]
        assert exponential_search(words, "cherry") == 2
        assert exponential_search(words, "apple") == 0
        assert exponential_search(words, "elderberry") == 4
        assert exponential_search(words, "fig") == -1

    def test_works_with_tuples_as_input(self):
        # The function should accept any sequence (e.g. tuple) not only lists.
        tup = (1, 3, 5, 7, 9)
        assert exponential_search(tup, 5) == 2
        assert exponential_search(tup, 4) == -1

    # --- sanity: result is consistent with the ``in`` operator ----------

    def test_matches_python_membership(self):
        import random

        random.seed(0)
        sorted_arr = sorted(random.sample(range(-200, 200), 50))
        for value in range(-210, 210, 7):
            expected = sorted_arr.index(value) if value in sorted_arr else -1
            assert exponential_search(sorted_arr, value) == expected