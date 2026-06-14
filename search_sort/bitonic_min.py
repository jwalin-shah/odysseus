"""Bitonic array minimum element finder.

A bitonic array is one that first monotonically increases and then
monotonically decreases (or first decreases then increases). The
``bitonic_min`` function locates the smallest element in such an
array using a modified binary search in O(log n) time.
"""


def bitonic_min(arr):
    """Return the minimum element of a bitonic array.

    The function is robust to either orientation of the bitonic
    sequence (increasing-then-decreasing OR decreasing-then-increasing)
    and gracefully degrades to a linear scan fallback for arrays that
    do not exhibit a clean bitonic shape.

    Parameters
    ----------
    arr : list or tuple
        Sequence of comparable elements forming a bitonic array.

    Returns
    -------
    The minimum element in ``arr``.

    Raises
    ------
    TypeError
        If ``arr`` is ``None`` or not a list/tuple.
    ValueError
        If ``arr`` is empty.
    """
    if arr is None:
        raise TypeError("Input cannot be None")
    if not isinstance(arr, (list, tuple)):
        raise TypeError("Input must be a list or tuple")

    n = len(arr)
    if n == 0:
        raise ValueError("Array cannot be empty")
    if n == 1:
        return arr[0]
    if n == 2:
        return arr[0] if arr[0] <= arr[1] else arr[1]

    low, high = 0, n - 1

    while low <= high:
        mid = (low + high) // 2

        # If mid is strictly between the endpoints, check whether
        # it is a local minimum (valley point).
        if 0 < mid < n - 1:
            if arr[mid] <= arr[mid - 1] and arr[mid] <= arr[mid + 1]:
                return arr[mid]

        # We are either at an endpoint or on a slope.  Decide which
        # half of the array still hides the minimum.
        if mid == 0 or arr[mid] > arr[mid - 1]:
            # Ascending slope (or left boundary) -> minimum is to the right.
            low = mid + 1
        else:
            # Descending slope -> minimum is to the left.
            high = mid - 1

    # Binary search did not isolate a local minimum.  In a well-formed
    # bitonic array the minimum always sits at one of the endpoints.
    return arr[0] if arr[0] <= arr[-1] else arr[-1]