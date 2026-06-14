import os
import sys

# Make the src/ package importable regardless of where pytest is invoked.
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src")),
)

from rotation_counter import rotation_count


def test_basic_rotation():
    """A classic rotated array: minimum is at index 2."""
    assert rotation_count([15, 18, 2, 3, 6, 12]) == 2


def test_no_rotation_sorted_array():
    """A fully sorted ascending array has 0 rotations."""
    assert rotation_count([1, 2, 3, 4, 5, 6, 7]) == 0


def test_empty_array_returns_zero():
    """Empty array should return 0."""
    assert rotation_count([]) == 0


def test_none_input_returns_zero():
    """None input should return 0 gracefully."""
    assert rotation_count(None) == 0


def test_single_element_returns_zero():
    """Single element array should return 0."""
    assert rotation_count([42]) == 0


def test_two_elements_rotated():
    """Two elements rotated once."""
    assert rotation_count([2, 1]) == 1


def test_two_elements_not_rotated():
    """Two elements already sorted."""
    assert rotation_count([1, 2]) == 0


def test_rotation_by_one_position():
    """Array rotated by one position to the right."""
    assert rotation_count([5, 1, 2, 3, 4]) == 1


def test_rotation_by_n_minus_one():
    """Array rotated by n-1 positions (minimum near the end)."""
    assert rotation_count([3, 4, 5, 1, 2]) == 3


def test_all_identical_elements():
    """Array of all same elements is not considered rotated."""
    assert rotation_count([7, 7, 7, 7, 7]) == 0


def test_negative_numbers():
    """Rotation with negative numbers."""
    assert rotation_count([-3, -2, -1, -5, -4]) == 3


def test_floating_point_numbers():
    """Rotation with floating point values."""
    assert rotation_count([1.5, 2.5, 3.5, 0.5, 1.0]) == 3


def test_string_values():
    """Rotation with string values."""
    assert rotation_count(["c", "d", "e", "a", "b"]) == 3


def test_rotation_in_middle():
    """Rotation where minimum sits in the middle of the original layout."""
    arr = [4, 5, 6, 7, 1, 2, 3]
    assert rotation_count(arr) == 4


def test_large_array_rotation():
    """Test with a larger rotated array (10-element rotation)."""
    arr = list(range(6, 16)) + list(range(1, 6))  # [6..15, 1..5]
    assert rotation_count(arr) == 10


def test_rotation_count_is_int():
    """Returned value must always be an integer."""
    result = rotation_count([4, 5, 1, 2, 3])
    assert isinstance(result, int)
    assert result == 2


def test_already_sorted_two_elements():
    """A length-2 sorted array returns 0."""
    assert rotation_count([10, 20]) == 0


def test_already_sorted_three_elements():
    """A length-3 sorted array returns 0."""
    assert rotation_count([10, 20, 30]) == 0