"""Search the leftmost index whose value is not less than a target.

This module exposes :func:`search_leftmost_not_less_than`, the
"lower bound" binary search: given a *non-decreasing* sequence, return
the smallest index ``i`` such that ``arr[i] >= target``.  If every
element is strictly less than ``target`` the function returns
``len(arr)`` (the conventional insertion position).
"""

from __future__ import annotations

from typing import Sequence, TypeVar

__all__ = ["search_leftmost_not_less_than"]

_T = TypeVar("_T")


def search_leftmost_not_less_than(arr: Sequence[_T], target: _T) -> int:
    """Return the leftmost index whose value is not less than ``target``.

    The sequence ``arr`` must be sorted in non-decreasing order.  This
    is the standard *lower bound* search (the C++ ``std::lower_bound``
    or Python ``bisect_left`` semantics).

    Parameters
    ----------
    arr : Sequence[_T]
        A sorted (non-decreasing) sequence of comparable elements.
    target : _T
        The value to search for.  It only needs to be comparable to the
        elements of ``arr``.

    Returns
    -------
    int
        The smallest index ``i`` such that ``arr[i] >= target``.  If
        every element of ``arr`` is strictly less than ``target`` the
        returned index equals ``len(arr)``.  For an empty sequence the
        result is always ``0``.

    Examples
    --------
    >>> search_leftmost_not_less_than([1, 3, 5, 7, 9], 5)
    2
    >>> search_leftmost_not_less_than([1, 3, 5, 7, 9], 4)
    2
    >>> search_leftmost_not_less_than([1, 3, 5, 7, 9], 0)
    0
    >>> search_leftmost_not_less_than([1, 3, 5, 7, 9], 10)
    5
    >>> search_leftmost_not_less_than([], 5)
    0
    """
    # Defensive copy of bounds so the caller can pass any Sequence type
    # (list, tuple, deque, custom sequence, ...).
    lo = 0
    hi = len(arr)

    # Classic lower-bound loop.  Invariant:
    #   arr[0..lo)   < target  (all strictly less)
    #   arr[hi..n)  >= target  (all not less)
    while lo < hi:
        # Using (lo + hi) // 2 is fine for Python ints (unbounded
        # precision) and avoids the well-known overflow pitfall from
        # other languages.  ``bisect`` uses lo + (hi - lo) // 2; both
        # are equivalent here.
        mid = (lo + hi) // 2
        if arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid

    return lo