import os
import sys

# Make the ``src`` directory importable regardless of how pytest is invoked.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from search_rotation_point import search_rotation_point  # noqa: E402


class TestSearchRotationPointBasic:
    def test_rotated_in_middle(self):
        """Classic example with the pivot somewhere in the middle."""
        assert search_rotation_point([15, 18, 2, 3, 6, 12]) == 2

    def test_rotated_near_end(self):
        """Pivot is one position before the end."""
        assert search_rotation_point([7, 9, 11, 12, 5]) == 4

    def test_rotated_at_index_4(self):
        """Larger example similar to the LeetCode 'find minimum' case."""
        assert search_rotation_point([4, 5, 6, 7, 0, 1, 2]) == 4

    def test_rotated_at_index_1(self):
        """Pivot is at the second position."""
        assert search_rotation_point([3, 1, 2]) == 1


class TestSearchRotationPointEdgeCases:
    def test_not_rotated_returns_zero(self):
        """An already-sorted array has its rotation point at index 0."""
        assert search_rotation_point([1, 2, 3, 4, 5, 6, 7]) == 0

    def test_empty_array_returns_minus_one(self):
        """Empty input has no rotation point."""
        assert search_rotation_point([]) == -1

    def test_single_element_returns_zero(self):
        """A one-element array trivially has its pivot at index 0."""
        assert search_rotation_point([42]) == 0

    def test_two_elements_rotated(self):
        assert search_rotation_point([2, 1]) == 1

    def test_two_elements_not_rotated(self):
        assert search_rotation_point([1, 2]) == 0

    def test_rotation_at_last_index(self):
        """Rotation point sits at the very last position."""
        assert search_rotation_point([2, 3, 4, 5, 1]) == 4

    def test_rotation_at_first_index(self):
        """Rotation point sits at the very first position."""
        assert search_rotation_point([6, 1, 2, 3, 4, 5]) == 1


class TestSearchRotationPointGeneric:
    def test_works_with_strings(self):
        """The implementation should work for any comparable type."""
        arr = ["cat", "dog", "elephant", "ant", "bear"]
        assert search_rotation_point(arr) == 3

    def test_works_with_negative_numbers(self):
        """Negative numbers are handled just like positives."""
        arr = [-3, -2, -1, -10, -9, -8, -7, -6, -5, -4]
        assert search_rotation_point(arr) == 3

    def test_does_not_mutate_input(self):
        """The function must leave the caller's list untouched."""
        arr = [15, 18, 2, 3, 6, 12]
        snapshot = list(arr)
        search_rotation_point(arr)
        assert arr == snapshot