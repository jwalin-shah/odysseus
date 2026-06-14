"""Find a peak element in an array using binary search.

A peak element is an element that is strictly greater than its neighbors.
For boundary elements, only one neighbor is considered: the first element
is a peak if it is greater than (or equal to) the second; the last element
is a peak if it is greater than (or equal to) the second-to-last.

The implementation runs in O(log n) time and O(1) space.
"""

from typing import List, Optional


def search_peak_finder(arr: List[int]) -> Optional[int]:
    """Return the index of a peak element in ``arr``, or ``None`` if empty.

    Uses an iterative binary search. When ``arr[mid] < arr[mid + 1]`` the
    peak must lie to the right of ``mid``; otherwise it lies at ``mid`` or
    to the left. This guarantees finding a valid peak.

    Parameters
    ----------
    arr : list[int]
        The input list of comparable elements.

    Returns
    -------
    int or None
        Index of a peak element, or ``None`` when ``arr`` is empty.
    """
    if not arr:
        return None

    n = len(arr)
    # Single element: by definition the element at index 0 is a peak.
    if n == 1:
        return 0

    # Check the boundaries explicitly to keep the binary search simple.
    if arr[0] >= arr[1]:
        return 0
    if arr[n - 1] >= arr[n - 2]:
        return n - 1

    lo, hi = 1, n - 2
    while lo <= hi:
        mid = (lo + hi) // 2
        # mid is a peak if it is at least as large as both neighbors.
        if arr[mid] >= arr[mid - 1] and arr[mid] >= arr[mid + 1]:
            return mid
        # Ascending slope: the peak is to the right.
        if arr[mid] < arr[mid + 1]:
            lo = mid + 1
        else:
            # Descending slope: the peak is to the left.
            hi = mid - 1

    # Fallback; the boundary checks above ensure this is unreachable
    # for non-empty input, but returning None keeps the contract safe.
    return None


__all__ = ["search_peak_finder"]