def rotation_count(arr):
    """
    Count the number of rotations in a rotated sorted array.

    A rotation is performed by moving the first element of a sorted array to
    the end. The number of rotations equals the index of the minimum element.

    This implementation uses a modified binary search for O(log n) time
    complexity on arrays with distinct elements.

    Args:
        arr: A list of comparable elements representing a rotated sorted
             array. Empty input, single-element input, or non-rotated input
             yields 0.

    Returns:
        int: The number of rotations (index of the minimum element).
             Returns 0 for empty / single-element arrays or unrotated arrays.

    Examples:
        >>> rotation_count([15, 18, 2, 3, 6, 12])
        2
        >>> rotation_count([1, 2, 3, 4, 5])
        0
        >>> rotation_count([])
        0
        >>> rotation_count([5, 1, 2, 3, 4])
        1
    """
    # Guard against empty input, None, and trivial single-element arrays.
    if not arr or len(arr) <= 1:
        return 0

    low, high = 0, len(arr) - 1

    # If the first element is smaller than the last, the array is already
    # sorted and therefore has zero rotations. This is the common case
    # for arrays with distinct (or strictly non-decreasing) elements.
    if arr[low] < arr[high]:
        return 0

    # Binary search: find the index of the minimum element. The minimum
    # of a rotated sorted array is the only element that is smaller than
    # the element immediately before it (wrapping around).
    while low < high:
        mid = (low + high) // 2

        if arr[mid] > arr[high]:
            # The pivot (minimum) must be strictly to the right of mid.
            low = mid + 1
        else:
            # The pivot is at mid or to the left of mid.
            high = mid

    return low