"""Locate the rightmost occurrence of a value in a sorted sequence.

This module exposes :func:`search_last_occurrence_locator`, a small utility
that uses an iterative binary search to find the last index at which a
target value appears in a non-decreasing sequence.  It runs in ``O(log n)``
time and ``O(1)`` additional space, and gracefully handles edge cases such
as empty input, missing values, and single-element sequences.
"""

from __future__ import annotations

from typing import Any, Sequence


def search_last_occurrence_locator(arr: Sequence[Any], target: Any) -> int:
    """Return the index of the *last* occurrence of ``target`` in ``arr``.

    The input sequence must be sorted in non-decreasing order.  The search
    narrows the candidate window with a classic binary search, but instead
    of stopping at the first match it continues to the right to find the
    rightmost position.

    Parameters
    ----------
    arr : Sequence[Any]
        A sorted (non-decreasing) sequence of comparable elements.  Lists
        and tuples are both accepted.  An empty sequence is allowed.
    target : Any
        The value to locate in ``arr``.

    Returns
    -------
    int
        The largest index ``i`` such that ``arr[i] == target``, or ``-1``
        if ``target`` does not occur in ``arr``.

    Examples
    --------
    >>> search_last_occurrence_locator([1, 2, 3, 3, 3, 4, 5], 3)
    4
    >>> search_last_occurrence_locator([1, 2, 3, 4, 5], 6)
    -1
    >>> search_last_occurrence_locator([], 0)
    -1
    """
    # Guard against empty input - the loop would never execute but the
    # explicit check makes the intent clear and avoids a subtle bug if a
    # caller passes something with a non-bool ``__len__`` result.
    if len(arr) == 0:
        return -1

    left, right = 0, len(arr) - 1
    result = -1

    while left <= right:
        # Using integer division avoids float rounding issues and works
        # for arbitrarily large indices.
        mid = (left + right) // 2

        if arr[mid] == target:
            # Record the match and keep searching to the right for a later
            # occurrence of the same value.
            result = mid
            left = mid + 1
        elif arr[mid] < target:
            left = mid + 1
        else:  # arr[mid] > target
            right = mid - 1

    return result