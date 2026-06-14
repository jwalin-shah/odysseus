from search.peak_finder import find_peak, peak_finder


def _is_peak(arr, idx, val):
    """Helper: check that arr[idx] == val and val is a peak."""
    if arr[idx] != val:
        return False
    n = len(arr)
    if idx > 0 and arr[idx - 1] > val:
        return False
    if idx < n - 1 and arr[idx + 1] > val:
        return False
    return True


def test_empty_array_returns_none():
    assert find_peak([]) is None
    assert peak_finder([]) is None


def test_single_element_array():
    assert find_peak([7]) == 7
    assert peak_finder([42]) == 42


def test_two_element_array_peak():
    # Either element is acceptable as a "peak" at the boundary.
    result = find_peak([1, 3])
    assert result in (1, 3)
    result = find_peak([5, 2])
    assert result in (5, 2)


def test_strictly_increasing_array():
    arr = [1, 2, 3, 4, 5, 6]
    # The last element is a boundary peak.
    result = find_peak(arr)
    assert result == 6


def test_strictly_decreasing_array():
    arr = [6, 5, 4, 3, 2, 1]
    # The first element is a boundary peak.
    result = find_peak(arr)
    assert result == 6


def test_array_with_clear_peak_in_middle():
    arr = [1, 3, 5, 4, 2]
    result = find_peak(arr)
    # 5 is a valid peak in this array.
    assert result == 5


def test_array_with_multiple_peaks():
    arr = [1, 5, 2, 6, 3, 7, 1]
    result = find_peak(arr)
    # The returned value must be an actual peak element.
    assert result in (5, 6, 7)


def test_flat_array():
    arr = [3, 3, 3, 3]
    result = find_peak(arr)
    assert result == 3


def test_result_is_actually_a_peak():
    arr = [1, 2, 1, 3, 5, 6, 4]
    result = find_peak(arr)
    # Find the index of the returned value.
    idx = arr.index(result)
    assert _is_peak(arr, idx, result), (
        f"Returned value {result} at index {idx} is not a valid peak"
    )


def test_result_is_actually_a_peak_2():
    arr = [10, 20, 15, 2, 23, 90, 67]
    result = find_peak(arr)
    idx = arr.index(result)
    assert _is_peak(arr, idx, result), (
        f"Returned value {result} at index {idx} is not a valid peak"
    )


def test_negative_values():
    arr = [-5, -1, -3, -7, -10]
    result = find_peak(arr)
    idx = arr.index(result)
    assert _is_peak(arr, idx, result)


def test_large_array_returns_valid_peak():
    arr = [1, 3, 2, 5, 4, 7, 6, 3, 2, 1, 0]
    result = find_peak(arr)
    # The returned value must be an actual peak element of the array.
    # Valid peaks here are 3, 5, 7, or 6 (any of these is acceptable).
    idx = arr.index(result)
    assert _is_peak(arr, idx, result), (
        f"Returned value {result} at index {idx} is not a valid peak"
    )
    assert result in (3, 5, 7, 6)


def test_peak_finder_alias_works():
    arr = [1, 2, 3, 2, 1]
    assert peak_finder(arr) == 3


def test_odd_length_array():
    arr = [1, 2, 3, 4, 5, 4, 3, 2, 1]
    result = find_peak(arr)
    idx = arr.index(result)
    assert _is_peak(arr, idx, result)
    assert result == 5