"""Tests for the rotation_point function."""

import os
import sys

# Add the project root to sys.path so we can import from search/
_PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from search.rotation_point import rotation_point


class TestRotationPoint:
    """Tests for the rotation_point function."""

    def test_basic_rotated_array(self):
        """A simple rotated array returns the index of its smallest element."""
        # Sorted: [2, 3, 6, 12, 15, 18]
        # Rotated at index 2 -> [15, 18, 2, 3, 6, 12]
        # Smallest element (2) is at index 2.
        assert rotation_point([15, 18, 2, 3, 6, 12]) == 2

    def test_rotated_at_index_one(self):
        """An array rotated near the beginning."""
        # Sorted: [1, 2, 3, 4, 5, 6, 7]
        # Rotated at index 5 -> [6, 7, 1, 2, 3, 4, 5]
        # Smallest element (1) is at index 2.
        assert rotation_point([6, 7, 1, 2, 3, 4, 5]) == 2

    def test_rotated_at_index_end(self):
        """An array rotated at the second-to-last position."""
        # Sorted: [1, 2, 3, 4, 5]
        # Rotated at index 4 -> [5, 1, 2, 3, 4]
        # Smallest element (1) is at index 1.
        assert rotation_point([5, 1, 2, 3, 4]) == 1

    def test_not_rotated_array(self):
        """A fully sorted array has rotation point 0."""
        assert rotation_point([1, 2, 3, 4, 5]) == 0

    def test_not_rotated_array_larger(self):
        """A larger fully sorted array has rotation point 0."""
        assert rotation_point([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) == 0

    def test_empty_array(self):
        """An empty array returns -1."""
        assert rotation_point([]) == -1

    def test_single_element_array(self):
        """A single-element array returns 0."""
        assert rotation_point([42]) == 0

    def test_two_elements_rotated(self):
        """A two-element rotated array."""
        # Sorted: [1, 2] -> rotated at index 1 -> [2, 1]
        # Smallest element (1) is at index 1.
        assert rotation_point([2, 1]) == 1

    def test_two_elements_not_rotated(self):
        """A two-element sorted array returns 0."""
        assert rotation_point([1, 2]) == 0

    def test_with_strings(self):
        """The function works with any comparable type (e.g. strings)."""
        # Sorted: ['ant', 'bird', 'cat', 'dog', 'elephant']
        # Rotated at k=2 -> ['cat', 'dog', 'elephant', 'ant', 'bird']
        # Smallest element ('ant') is at index 3.
        assert rotation_point(["cat", "dog", "elephant", "ant", "bird"]) == 3

    def test_with_negative_numbers(self):
        """The function works with negative numbers."""
        # Sorted: [-5, -2, 0, 3, 7]
        # Rotated at k=3 -> [3, 7, -5, -2, 0]
        # Smallest element (-5) is at index 2.
        assert rotation_point([3, 7, -5, -2, 0]) == 2

    def test_with_floats(self):
        """The function works with floating point numbers."""
        # Sorted: [0.1, 0.5, 1.0, 1.5, 2.0]
        # Rotated at k=2 -> [1.0, 1.5, 2.0, 0.1, 0.5]
        # Smallest element (0.1) is at index 3.
        assert rotation_point([1.0, 1.5, 2.0, 0.1, 0.5]) == 3

    def test_rotated_by_one(self):
        """An array rotated by a single position."""
        # Sorted: [1, 2, 3, 4, 5, 6]
        # Rotated by 1 -> [6, 1, 2, 3, 4, 5]
        # Smallest element (1) is at index 1.
        assert rotation_point([6, 1, 2, 3, 4, 5]) == 1

    def test_large_rotated_array(self):
        """A larger rotated array."""
        # Sorted: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        # Rotated at k=7 -> [8, 9, 10, 11, 12, 13, 14, 15, 1, 2, 3, 4, 5, 6, 7]
        # Smallest element (1) is at index 8.
        arr = [8, 9, 10, 11, 12, 13, 14, 15, 1, 2, 3, 4, 5, 6, 7]
        assert rotation_point(arr) == 8

    @pytest.mark.parametrize(
        "arr,expected",
        [
            ([], -1),
            ([1], 0),
            ([1, 2], 0),
            ([2, 1], 1),
            ([1, 2, 3, 4, 5], 0),
            ([3, 4, 5, 1, 2], 3),
            ([4, 5, 6, 7, 0, 1, 2], 4),
            ([15, 18, 2, 3, 6, 12], 2),
            ([5, 1, 2, 3, 4], 1),
        ],
    )
    def test_parametrized(self, arr, expected):
        """Parametrized tests covering many edge cases."""
        assert rotation_point(arr) == expected