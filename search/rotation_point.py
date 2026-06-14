"""Find the rotation point in a rotated sorted array.

A "rotation point" of a sorted array that has been rotated at some pivot
is the index of the smallest element in the array. If the array was never
rotated, the rotation point is 0.
"""


def rotation_point(arr):
    """Return the index of the rotation point of a rotated sorted array.

    The input ``arr`` is assumed to be a list of comparable elements that
    was originally sorted in ascending order and then rotated at some
    pivot ``k`` (where ``k`` can be ``0`` for a non-rotated array). The
    function returns the index of the smallest element, which is the
    rotation point.

    Parameters
    ----------
    arr : list
        A rotated sorted array. Assumed to contain distinct elements.

    Returns
    -------
    int
        The index of the smallest element (the rotation point), or
        ``-1`` if the array is empty.

    Examples
    --------
    >>> rotation_point([15, 18, 2, 3, 6, 12])
    2
    >>> rotation_point([1, 2, 3, 4, 5])
    0
    >>> rotation_point([])
    -1
    """
    if not arr:
        return -1

    left, right = 0, len(arr) - 1

    # If the leftmost element is <= the rightmost element, the array
    # is not rotated (or rotated by 0), so the smallest element is at
    # the start.
    if arr[left] <= arr[right]:
        return left

    while left <= right:
        mid = (left + right) // 2

        # The element at mid+1 is the rotation point if it is smaller
        # than the element at mid.
        if mid < right and arr[mid] > arr[mid + 1]:
            return mid + 1

        # The element at mid is the rotation point if it is smaller
        # than the element at mid-1.
        if mid > left and arr[mid - 1] > arr[mid]:
            return mid

        # Decide which half contains the rotation point.
        if arr[left] <= arr[mid]:
            # Left half is sorted, so the rotation point is in the
            # right half.
            left = mid + 1
        else:
            # Right half is sorted, so the rotation point is in the
            # left half.
            right = mid - 1

    # Should not be reached for a valid rotated sorted array.
    return -1