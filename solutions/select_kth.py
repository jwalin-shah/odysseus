"""Selection algorithm for finding the k-th smallest element.

Implements quickselect with a median-of-three pivot strategy, giving
average-case O(n) time complexity and O(1) auxiliary space.
"""

from __future__ import annotations

from typing import Sequence, TypeVar

T = TypeVar("T")


def select_kth(arr: Sequence[T], k: int) -> T:
    """Return the k-th smallest element of ``arr`` (0-indexed).

    Parameters
    ----------
    arr:
        A non-empty sequence of mutually comparable elements.
    k:
        Zero-based rank of the element to retrieve. ``k=0`` yields the
        minimum and ``k=len(arr)-1`` yields the maximum.

    Returns
    -------
    The k-th smallest element of ``arr``.

    Raises
    ------
    IndexError
        If ``arr`` is empty or ``k`` is outside ``[0, len(arr))``.

    Notes
    -----
    The input sequence is not mutated; an internal copy is sorted
    in-place by the algorithm.
    """
    n = len(arr)
    if n == 0:
        raise IndexError("select_kth() arg is an empty sequence")
    if not isinstance(k, int) or isinstance(k, bool):
        raise TypeError("k must be an integer")
    if k < 0 or k >= n:
        raise IndexError(
            f"k={k} is out of range for sequence of length {n}"
        )

    # Work on a copy so the caller's data is preserved.
    a = list(arr)
    return _quickselect(a, 0, n - 1, k)


def _quickselect(a: list, left: int, right: int, k: int):
    """Iterative quickselect driver.

    Repeatedly partitions ``a[left:right+1]`` until the element at
    index ``k`` is the k-th smallest of the sub-range, then returns it.
    """
    while left < right:
        pivot_index = _partition(a, left, right)
        if k == pivot_index:
            return a[k]
        if k < pivot_index:
            right = pivot_index - 1
        else:
            left = pivot_index + 1
    return a[left]


def _partition(a: list, left: int, right: int) -> int:
    """Lomuto partition using a median-of-three pivot.

    Returns the final index of the pivot element.
    """
    mid = (left + right) // 2

    # Order a[left], a[mid], a[right] so the median is at a[mid].
    if a[left] > a[mid]:
        a[left], a[mid] = a[mid], a[left]
    if a[left] > a[right]:
        a[left], a[right] = a[right], a[left]
    if a[mid] > a[right]:
        a[mid], a[right] = a[right], a[mid]

    # Move the median pivot to the rightmost position for Lomuto.
    a[mid], a[right] = a[right], a[mid]
    pivot = a[right]

    i = left
    for j in range(left, right):
        if a[j] <= pivot:
            a[i], a[j] = a[j], a[i]
            i += 1
    a[i], a[right] = a[right], a[i]
    return i