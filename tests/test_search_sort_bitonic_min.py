import pytest

from src.search_sort_bitonic_min import search_sort_bitonic_min


def test_single_element():
    """A single-element array should return that element."""
    assert search_sort_bitonic_min([5]) == 5


def test_two_elements_increasing():
    """Two-element array that is increasing - min is the first element."""
    assert search_sort_bitonic_min([1, 2]) == 1


def test_two_elements_decreasing():
    """Two-element array that is decreasing - min is the second element."""
    assert search_sort_bitonic_min([2, 1]) == 1


def test_classic_bitonic_min_at_start():
    """Classic bitonic array where the minimum is at the start.

    Array: 1, 3, 5, 7, 6, 4, 2  (bitonic point / max is at index 3)
    """
    assert search_sort_bitonic_min([1, 3, 5, 7, 6, 4, 2]) == 1


def test_bitonic_min_at_end():
    """Bitonic array where the minimum is at the end.

    Array: 2, 4, 6, 7, 5, 3, 1  (bitonic point / max is at index 3)
    """
    assert search_sort_bitonic_min([2, 4, 6, 7, 5, 3, 1]) == 1


def test_bitonic_with_negative_numbers():
    """Bitonic array containing negative numbers."""
    assert search_sort_bitonic_min([-5, -2, 0, 3, 2, 1, -1]) == -5


def test_bitonic_with_equal_endpoints():
    """Bitonic array where both endpoints have the same value."""
    # 1, 3, 5, 7, 5, 3, 1  - both ends are 1
    assert search_sort_bitonic_min([1, 3, 5, 7, 5, 3, 1]) == 1


def test_bitonic_long_array():
    """Longer bitonic array to verify correctness at scale.

    Bitonic point is the maximum value 10.
    """
    arr = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 9, 8, 7, 6, 5, 4, 3, 2, 1]
    assert search_sort_bitonic_min(arr) == 1


def test_empty_array_raises_value_error():
    """An empty array should raise ValueError."""
    with pytest.raises(ValueError):
        search_sort_bitonic_min([])


def test_non_list_input_raises_type_error():
    """A non-list, non-tuple input should raise TypeError."""
    with pytest.raises(TypeError):
        search_sort_bitonic_min("not a list")


def test_none_input_raises_type_error():
    """A None input should raise TypeError."""
    with pytest.raises(TypeError):
        search_sort_bitonic_min(None)


def test_tuple_input_works():
    """Tuples should also be accepted as input."""
    assert search_sort_bitonic_min((1, 3, 5, 7, 6, 4, 2)) == 1


def test_bitonic_with_floats():
    """Bitonic array of floating-point numbers."""
    arr = [0.1, 0.5, 0.9, 1.2, 0.8, 0.4, 0.05]
    assert search_sort_bitonic_min(arr) == 0.05