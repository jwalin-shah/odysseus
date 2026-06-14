"""Tests for ``search_sort.bitonic_min.bitonic_min``."""
import os
import sys

import pytest

# Make the project root importable so ``search_sort`` resolves when
# pytest is invoked from any working directory.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from search_sort.bitonic_min import bitonic_min  # noqa: E402


# ---------------------------------------------------------------------------
# Standard bitonic shapes
# ---------------------------------------------------------------------------


def test_increasing_then_decreasing_classic_example():
    """Classic bitonic example - min is at the start."""
    arr = [1, 3, 5, 7, 6, 4, 2]
    assert bitonic_min(arr) == 1


def test_decreasing_then_increasing_bitonic():
    """Bitonic that descends then ascends - min is at the valley."""
    arr = [7, 5, 3, 2, 4, 6, 8]
    assert bitonic_min(arr) == 2


def test_larger_bitonic_array():
    """Larger bitonic array with the peak in the middle."""
    arr = [1, 3, 5, 7, 9, 11, 10, 8, 6, 4, 2]
    assert bitonic_min(arr) == 1


def test_min_at_end_when_decrease_drops_below_start():
    """When the descending tail falls below the starting value."""
    arr = [1, 2, 3, 4, 3, 2, 0]
    assert bitonic_min(arr) == 0


def test_negative_numbers_bitonic():
    """Bitonic array containing negative numbers."""
    arr = [-5, -3, 0, 5, 3, 1, -2]
    assert bitonic_min(arr) == -5


def test_floating_point_bitonic():
    """Bitonic array of floats."""
    arr = [1.5, 2.5, 3.5, 2.0, 1.0]
    assert bitonic_min(arr) == 1.0


def test_duplicate_values_bitonic():
    """Bitonic array that contains duplicate elements."""
    arr = [1, 3, 5, 5, 3, 1]
    assert bitonic_min(arr) == 1


# ---------------------------------------------------------------------------
# Trivial and degenerate sizes
# ---------------------------------------------------------------------------


def test_single_element():
    """Single-element array returns that element."""
    assert bitonic_min([42]) == 42


def test_two_elements_ascending():
    """Two ascending elements return the smaller one."""
    assert bitonic_min([1, 2]) == 1


def test_two_elements_descending():
    """Two descending elements return the smaller one."""
    assert bitonic_min([2, 1]) == 1


def test_fully_increasing_array():
    """Monotonically increasing array - min is the first element."""
    assert bitonic_min([1, 2, 3, 4, 5, 6, 7]) == 1


def test_fully_decreasing_array():
    """Monotonically decreasing array - min is the last element."""
    assert bitonic_min([7, 6, 5, 4, 3, 2, 1]) == 1


def test_all_equal_values():
    """All-equal array returns that common value."""
    assert bitonic_min([5, 5, 5, 5, 5]) == 5


def test_three_element_increasing():
    """Three-element strictly increasing array."""
    assert bitonic_min([10, 20, 30]) == 10


def test_three_element_decreasing():
    """Three-element strictly decreasing array."""
    assert bitonic_min([30, 20, 10]) == 10


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_empty_array_raises_value_error():
    """Empty arrays should be rejected with ``ValueError``."""
    with pytest.raises(ValueError):
        bitonic_min([])


def test_none_input_raises_type_error():
    """``None`` should be rejected with ``TypeError``."""
    with pytest.raises(TypeError):
        bitonic_min(None)


def test_string_input_raises_type_error():
    """Non-sequence scalars must raise ``TypeError``."""
    with pytest.raises(TypeError):
        bitonic_min("not a list")


def test_integer_input_raises_type_error():
    """Raw integers are not valid sequences for this function."""
    with pytest.raises(TypeError):
        bitonic_min(42)


# ---------------------------------------------------------------------------
# Sanity / structural checks
# ---------------------------------------------------------------------------


def test_returns_int_for_int_input():
    """The result preserves the numeric type of the input."""
    result = bitonic_min([3, 5, 4, 2, 1])
    assert isinstance(result, int)
    assert result == 1


def test_result_is_minimum_versus_python_builtin():
    """The function agrees with the built-in ``min`` for many inputs."""
    arrays = [
        [1, 3, 5, 7, 6, 4, 2],
        [7, 5, 3, 2, 4, 6, 8],
        [1, 2, 3, 4, 3, 2, 0],
        [-5, -3, 0, 5, 3, 1, -2],
        [1, 1, 1, 1, 1],
        [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
    ]
    for arr in arrays:
        assert bitonic_min(arr) == min(arr)


def test_accepts_tuple_input():
    """The function should also accept tuples, not just lists."""
    assert bitonic_min((5, 4, 3, 2, 1)) == 1
    assert bitonic_min((1, 3, 5, 3, 1)) == 1