"""Inversion counter using a modified merge sort.

An *inversion* in a sequence is a pair of indices (i, j) such that
``i < j`` and ``arr[i] > arr[j]``.  Counting inversions naively is
``O(n^2)``; the classic divide-and-conquer approach below runs in
``O(n log n)`` time and ``O(n)`` extra space by counting cross-inversions
during the merge step of merge sort.

The public function is :func:`count_inversions`.  The helper
``count_inversions_inplace`` is also exposed for callers that want to
mutate an input list in place while obtaining the same count.
"""

from __future__ import annotations

from typing import List, MutableSequence, Sequence


def count_inversions(arr: Sequence[int]) -> int:
    """Return the number of inversions in ``arr``.

    The input sequence is not modified.  Non-sequence inputs raise
    ``TypeError``; an empty sequence or a sequence with a single
    element contains no inversions and returns ``0``.
    """
    if arr is None:
        return 0
    if not isinstance(arr, (list, tuple)):
        raise TypeError("count_inversions expects a list or tuple of comparable items")

    n = len(arr)
    if n < 2:
        return 0

    # Work on a copy so the caller's data is preserved.
    work = list(arr)
    return _merge_sort_count(work, 0, n - 1)


def count_inversions_inplace(arr: MutableSequence[int]) -> int:
    """Count inversions in ``arr`` while sorting it in place.

    Returns the inversion count.  After the call, ``arr`` will be sorted
    in ascending order.  This is the same algorithm as
    :func:`count_inversions` but it avoids the extra copy.
    """
    if arr is None:
        return 0
    n = len(arr)
    if n < 2:
        return 0
    return _merge_sort_count(arr, 0, n - 1)


# ---------------------------------------------------------------------------
# Internal merge-sort-based counting
# ---------------------------------------------------------------------------

def _merge_sort_count(arr: List[int], left: int, right: int) -> int:
    """Recursively count inversions within ``arr[left:right+1]``."""
    if left >= right:
        return 0

    mid = (left + right) // 2
    inv = _merge_sort_count(arr, left, mid)
    inv += _merge_sort_count(arr, mid + 1, right)
    inv += _merge_and_count(arr, left, mid, right)
    return inv


def _merge_and_count(arr: List[int], left: int, mid: int, right: int) -> int:
    """Merge the two sorted halves ``[left..mid]`` and ``[mid+1..right]``
    while counting how many elements in the left half are greater than
    each element pulled from the right half.
    """
    left_part = arr[left:mid + 1]
    right_part = arr[mid + 1:right + 1]

    i = j = 0
    k = left
    inv = 0

    while i < len(left_part) and j < len(right_part):
        if left_part[i] <= right_part[j]:
            arr[k] = left_part[i]
            i += 1
        else:
            arr[k] = right_part[j]
            # Every element still in ``left_part`` starting at index ``i``
            # forms an inversion with ``right_part[j]``.
            inv += len(left_part) - i
            j += 1
        k += 1

    # Drain any leftovers; no more inversions can be created here.
    while i < len(left_part):
        arr[k] = left_part[i]
        i += 1
        k += 1
    while j < len(right_part):
        arr[k] = right_part[j]
        j += 1
        k += 1

    return inv


__all__ = ["count_inversions", "count_inversions_inplace"]