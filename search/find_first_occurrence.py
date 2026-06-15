"""Binary search helpers for sorted integer arrays."""

from bisect import bisect_left
from typing import List


def find_first_occurrence(arr: List[int], target: int) -> int:
    """Return the index of the first occurrence of ``target`` in a sorted list.

    The list ``arr`` is assumed to be sorted in non-decreasing order. If
    ``target`` appears one or more times, the lowest index ``i`` with
    ``arr[i] == target`` is returned. If ``target`` is not present, ``-1`` is
    returned.

    Uses :func:`bisect.bisect_left` to find the lower bound in O(log n) and
    then verifies the slot actually holds ``target`` (since the list is sorted
    but not necessarily dense or non-empty).
    """
    if not arr:
        return -1
    idx = bisect_left(arr, target)
    if idx < len(arr) and arr[idx] == target:
        return idx
    return -1
