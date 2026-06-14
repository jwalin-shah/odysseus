"""
last_occurrence_locator
======================

Provides :func:`last_occurrence_locator`, a binary-search based helper that
returns the index of the *last* occurrence of a value inside a sorted
sequence (or ``-1`` if the value is absent).

The implementation is intentionally lightweight and has no external
dependencies so it can be reused in isolation by other modules.
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence


def last_occurrence_locator(arr: Optional[Sequence[Any]], target: Any) -> int:
    """Return the index of the last occurrence of ``target`` in ``arr``.

    The input is expected to be a *sorted* sequence.  When the target
    appears multiple times the rightmost index is returned.  When the
    target is not present (or the sequence is empty/``None``) the
    function returns ``-1``.

    Parameters
    ----------
    arr:
        Sorted sequence of comparable elements, or ``None``.
    target:
        The value to locate.  Comparison with sequence elements is done
        using the regular ``<`` / ``==`` / ``>`` operators.

    Returns
    -------
    int
        The index of the last occurrence of ``target``, or ``-1`` if it
        is not found.

    Examples
    --------
    >>> last_occurrence_locator([1, 2, 2, 2, 3, 4], 2)
    3
    >>> last_occurrence_locator([1, 2, 3, 4, 5], 6)
    -1
    >>> last_occurrence_locator([], 1)
    -1
    >>> last_occurrence_locator(None, 1)
    -1
    """
    # Guard against ``None`` and empty sequences up-front so the rest of
    # the routine can assume a non-empty, indexable container.
    if arr is None or len(arr) == 0:
        return -1

    left, right = 0, len(arr) - 1
    result = -1

    # Classic binary search.  When we hit the target we record the index
    # but keep searching to the right in case there are duplicates.
    while left <= right:
        mid = left + (right - left) // 2  # overflow-safe midpoint
        try:
            mid_value = arr[mid]
        except (IndexError, TypeError):
            # Defensive: if the sequence isn't indexable, bail out.
            return result

        if mid_value == target:
            result = mid
            left = mid + 1
        elif mid_value < target:
            left = mid + 1
        else:  # mid_value > target
            right = mid - 1

    return result


__all__ = ["last_occurrence_locator"]