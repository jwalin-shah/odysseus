"""Exponential search implementation.

Exponential search (also called doubling or galloping search) finds the
position of a target value within a *sorted* sequence by first locating a
range in which the target may lie -- by repeatedly doubling an index --
and then performing a binary search inside that range.

Time complexity:  O(log n)
Space complexity: O(1)  (iterative)
"""

from typing import Any, List, Sequence


def exponential_search(arr: Sequence[Any], target: Any) -> int:
    """Return the index of ``target`` in sorted ``arr`` using exponential search.

    If ``target`` is not present, or ``arr`` is empty, ``-1`` is returned.
    When the sequence contains duplicates, the implementation returns the
    index of the *first* occurrence.

    Parameters
    ----------
    arr : Sequence[Any]
        A sorted sequence (list, tuple, ...) of comparable elements.
    target : Any
        The value to search for.

    Returns
    -------
    int
        The 0-based index of ``target`` in ``arr``, or ``-1`` if not found.
    """
    n = len(arr)

    # Edge case: empty sequence.
    if n == 0:
        return -1

    # If the target happens to be the very first element, we are done.
    if arr[0] == target:
        return 0

    # Find the upper bound of the range by doubling the index.
    # Stop when we either run off the end of the array or the value at
    # the current index has already surpassed the target.
    i = 1
    while i < n and arr[i] <= target:
        i *= 2

    # Binary search the candidate window [i // 2, min(i, n - 1)].
    left, right = i // 2, min(i, n - 1)
    while left <= right:
        mid = (left + right) // 2
        mid_val = arr[mid]
        if mid_val == target:
            # Walk backwards to find the *first* occurrence in case of duplicates.
            while mid > 0 and arr[mid - 1] == target:
                mid -= 1
            return mid
        if mid_val < target:
            left = mid + 1
        else:
            right = mid - 1

    return -1


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    sample = [1, 3, 5, 7, 9, 11, 13, 15, 17, 19, 21]
    for value in (1, 11, 21, 0, 22, 13):
        print(f"exponential_search({value}) -> {exponential_search(sample, value)}")