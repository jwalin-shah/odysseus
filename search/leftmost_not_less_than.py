"""Binary search: leftmost element not less than a target value.

Given a sorted (non-decreasing) sequence ``arr`` and a value ``target``,
``leftmost_not_less_than`` returns the smallest index ``i`` such that
``arr[i] >= target``. If every element of ``arr`` is strictly less than
``target`` then ``len(arr)`` is returned — the position at which
``target`` would be inserted to keep the array sorted.
"""

from typing import Sequence, TypeVar

T = TypeVar("T")


def leftmost_not_less_than(arr: Sequence[T], target: T) -> int:
    """Return the leftmost index of an element not less than ``target``.

    The input sequence must be sorted in non-decreasing order.
    If no element is ``>= target``, the function returns ``len(arr)``,
    which is the insertion point that would keep ``arr`` sorted.

    Parameters
    ----------
    arr : Sequence[T]
        A non-empty or empty sequence sorted in non-decreasing order.
    target : T
        The value to search for.

    Returns
    -------
    int
        The smallest index ``i`` with ``arr[i] >= target``,
        or ``len(arr)`` if every element is strictly smaller.

    Examples
    --------
    >>> leftmost_not_less_than([1, 2, 4, 5, 6], 3)
    2
    >>> leftmost_not_less_than([1, 2, 2, 2, 3], 2)
    1
    >>> leftmost_not_less_than([1, 2, 3], 10)
    3
    """
    lo, hi = 0, len(arr)
    while lo < hi:
        mid = (lo + hi) // 2
        if arr[mid] < target:
            lo = mid + 1
        else:
            hi = mid
    return lo


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    sample = [1, 2, 2, 2, 3, 4, 5]
    for t in [0, 1, 2, 3, 4, 5, 6, 10]:
        print(f"target={t} -> {leftmost_not_less_than(sample, t)}")