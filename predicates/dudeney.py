"""Dudeney number predicate.

A Dudeney number is a positive integer that is a perfect cube whose decimal
digit sum equals the cube root. The first few are:

    1      =  1^3,  digit sum  1
    512    =  8^3,  digit sum  8
    4913   = 17^3,  digit sum 17
    5832   = 18^3,  digit sum 18
    17576  = 26^3,  digit sum 26
    19683  = 27^3,  digit sum 27
"""

from __future__ import annotations


def _integer_cube_root(n: int) -> int:
    """Return the integer ``k`` with ``k**3 == n``, or ``-1`` if none exists.

    Uses an exact binary search so the result is correct for arbitrarily large
    inputs (the floating-point ``n ** (1/3)`` shortcut loses precision past
    roughly 10**18).
    """
    if n < 0:
        return -1
    if n == 0:
        return 0

    lo, hi = 0, 1
    while hi * hi * hi < n:
        hi <<= 1  # double the upper bound until it overshoots

    # Invariant: lo**3 < n <= hi**3
    while lo < hi:
        mid = (lo + hi) // 2
        mid_cubed = mid * mid * mid
        if mid_cubed < n:
            lo = mid + 1
        else:
            hi = mid
    return lo if lo * lo * lo == n else -1


def _digit_sum(n: int) -> int:
    """Return the sum of the decimal digits of ``n`` (non-negative)."""
    s = 0
    while n > 0:
        s += n % 10
        n //= 10
    return s


def is_dudeney(n: int) -> bool:
    """Return ``True`` iff ``n`` is a Dudeney number.

    A Dudeney number is a positive integer ``n`` such that ``n = k**3`` and
    the sum of the decimal digits of ``n`` equals ``k``. Values outside the
    positive-integer domain (``n < 1`` or non-``int``) return ``False``.
    """
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        return False
    k = _integer_cube_root(n)
    if k < 1:
        return False
    return _digit_sum(n) == k
