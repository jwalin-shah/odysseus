"""Ternary stairs: count the number of distinct ways to climb a staircase
of ``n`` steps when you may take 1, 2, or 3 steps at a time.

The name comes from the fact that the climber has three (ternary) possible
step sizes.  The recurrence relation is::

    f(0) = 1            # one way to stand still
    f(1) = 1            # (1)
    f(2) = 2            # (1+1), (2)
    f(n) = f(n-1) + f(n-2) + f(n-3)   for n >= 3

This module exposes :func:`ternary_stairs` which computes ``f(n)`` in
``O(n)`` time and ``O(1)`` extra space using a rolling window of the
last three values.
"""

from __future__ import annotations

from typing import Union

# A small sentinel module-level constant is handy for tests / debugging
# and documents the closed form for the first few values.
_KNOWN_VALUES = (1, 1, 2, 4, 7, 13, 24, 44, 81, 149, 274, 504, 927, 1705, 3136)


def ternary_stairs(n: int) -> int:
    """Return the number of distinct ways to climb ``n`` stairs.

    You may take 1, 2, or 3 stairs in a single move.  The function uses
    a constant-space dynamic-programming loop.

    Parameters
    ----------
    n : int
        The number of stairs.  Negative inputs yield ``0`` (there is no
        way to climb a negative number of steps).

    Returns
    -------
    int
        The number of distinct sequences of 1/2/3-step moves that sum to
        exactly ``n``.

    Examples
    --------
    >>> ternary_stairs(0)
    1
    >>> ternary_stairs(3)
    4
    >>> ternary_stairs(4)
    7
    >>> ternary_stairs(10)
    274
    """
    # Negative or non-integer inputs: we only support non-negative ints.
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError(f"n must be an int, got {type(n).__name__}")
    if n < 0:
        return 0

    # Base cases: f(0), f(1), f(2).
    if n <= 2:
        return _KNOWN_VALUES[n]

    # Rolling window over the last three values keeps memory at O(1).
    #   a == f(i-3), b == f(i-2), c == f(i-1)
    a, b, c = 1, 1, 2
    for _ in range(3, n + 1):
        a, b, c = b, c, a + b + c
    return c


__all__ = ["ternary_stairs"]


if __name__ == "__main__":  # pragma: no cover - manual sanity check
    import sys

    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            print(f"ternary_stairs({arg}) = {ternary_stairs(int(arg))}")
    else:
        for i in range(11):
            print(f"f({i}) = {ternary_stairs(i)}")