"""Josephus problem solvers.

The Josephus problem is a counting-out game: ``n`` people stand in a circle
and every ``k``-th person is eliminated until only one remains.  This module
exposes two functions:

* :func:`josephus`         - returns the 1-indexed position of the last
  survivor.
* :func:`josephus_sequence` - returns the full elimination order.

Both functions use 1-indexed positions and start counting at position 1,
eliminating position ``k`` first.

Examples
--------
>>> josephus(5, 2)
3
>>> josephus(7, 3)
4
>>> josephus_sequence(5, 2)
[2, 4, 1, 5, 3]
"""

from __future__ import annotations

from typing import List


__all__ = ["josephus", "josephus_sequence"]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _validate(n: int, k: int) -> None:
    """Raise :class:`TypeError` or :class:`ValueError` for bad inputs.

    ``bool`` is explicitly rejected because ``isinstance(True, int)`` is
    ``True`` in Python and would otherwise sneak through the type check.
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("n must be an integer")
    if isinstance(k, bool) or not isinstance(k, int):
        raise TypeError("k must be an integer")
    if n < 1:
        raise ValueError("n must be a positive integer (>= 1)")
    if k < 1:
        raise ValueError("k must be a positive integer (>= 1)")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def josephus(n: int, k: int) -> int:
    """Return the 1-indexed position of the last survivor.

    ``n`` people numbered from 1 to ``n`` stand in a circle.  Starting at
    position 1, every ``k``-th person is eliminated (position ``k`` first,
    counting then resumes at the next person).  The function returns the
    position of the person who survives.

    The implementation uses the classic O(n) iterative recurrence

    .. math::

        J(1, k) = 0 \\\\
        J(i, k) = (J(i - 1, k) + k) \\bmod i

    where ``J`` is 0-indexed.  The result is returned 1-indexed.

    Parameters
    ----------
    n : int
        Number of people.  Must be ``>= 1``.
    k : int
        Counting step.  Must be ``>= 1``.

    Returns
    -------
    int
        1-indexed position of the survivor.

    Raises
    ------
    TypeError
        If ``n`` or ``k`` is not an integer.
    ValueError
        If ``n`` < 1 or ``k`` < 1.

    Examples
    --------
    >>> josephus(5, 2)
    3
    >>> josephus(1, 100)
    1
    >>> josephus(10, 1)
    10
    """
    _validate(n, k)
    result = 0
    for i in range(1, n + 1):
        result = (result + k) % i
    return result + 1


def josephus_sequence(n: int, k: int) -> List[int]:
    """Return the elimination order as a list of 1-indexed positions.

    The first element of the returned list is the first person eliminated,
    and the final element is the survivor.  This is a straightforward
    list-based simulation that mirrors the textbook description and is
    useful for testing/visualisation.

    Parameters
    ----------
    n : int
        Number of people.  Must be ``>= 1``.
    k : int
        Counting step.  Must be ``>= 1``.

    Returns
    -------
    list of int
        Elimination order.  The last element is the survivor.

    Raises
    ------
    TypeError
        If ``n`` or ``k`` is not an integer.
    ValueError
        If ``n`` < 1 or ``k`` < 1.

    Examples
    --------
    >>> josephus_sequence(5, 2)
    [2, 4, 1, 5, 3]
    >>> josephus_sequence(7, 3)
    [3, 6, 2, 7, 5, 1, 4]
    """
    _validate(n, k)
    people = list(range(1, n + 1))
    order: List[int] = []
    idx = 0
    while people:
        idx = (idx + k - 1) % len(people)
        order.append(people.pop(idx))
    return order


# ---------------------------------------------------------------------------
# Interactive demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    # Quick visual demo when run as a script.
    for n, k in [(5, 2), (7, 3), (6, 5), (41, 3)]:
        seq = josephus_sequence(n, k)
        print(f"n={n:>2}, k={k}: survivor={seq[-1]}, order={seq}")