"""Exponential search implementation.

Exponential search (also known as doubling search or galloping search) is
an algorithm for finding the position of a target value within a sorted
array. It works in two phases:

1. Identify a range ``[i // 2, i)`` in which the target may reside by
   repeatedly doubling an index (``1, 2, 4, 8, ...``) until the value at
   that index exceeds the target (or the end of the array is reached).
2. Run a standard binary search within that range.

The algorithm runs in ``O(log i)`` time, where ``i`` is the position of
the target. It is particularly useful for unbounded (or very large)
sorted arrays because it locates the bounds in logarithmic time without
needing to know the length of the array up front.
"""

from __future__ import annotations

from typing import List, Optional, TypeVar

T = TypeVar("T")


def exponential_search(arr: List[T], target: T) -> int:
    """Return the index of ``target`` in sorted ``arr`` or ``-1`` if absent.

    Parameters
    ----------
    arr:
        A non-decreasing list of comparable elements. The list does not
        need to be strictly sorted - duplicate values are permitted, in
        which case the returned index may correspond to any matching
        element.
    target:
        The value to look for.

    Returns
    -------
    int
        The index of ``target`` inside ``arr`` if found, otherwise ``-1``.

    Examples
    --------
    >>> exponential_search([1, 2, 3, 4, 5], 4)
    3
    >>> exponential_search([1, 2, 3, 4, 5], 6)
    -1
    >>> exponential_search([], 1)
    -1
    """
    # Edge case: nothing to search.
    if not arr:
        return -1

    n = len(arr)

    # Fast path: the very first element matches.
    if arr[0] == target:
        return 0

    # Phase 1 - gallop forward, doubling ``i`` each step, until the
    # element at ``i`` is greater than ``target`` (or we run off the end
    # of the array). The target, if present, must live in
    # ``[i // 2, min(i, n - 1)]``.
    i = 1
    while i < n and arr[i] <= target:
        i *= 2

    # Phase 2 - binary search inside the discovered range.
    left = i // 2
    right = min(i, n - 1)

    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        if arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1