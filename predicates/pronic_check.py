"""Pronic (oblong) number predicate.

A pronic number -- also called an *oblong* number -- is a number that can be
written as the product of two consecutive non-negative integers:

    x = k * (k + 1)        for some integer k >= 0

The first few pronic numbers are:
    0, 2, 6, 12, 20, 30, 42, 56, 72, 90, 110, ...

This module exposes a single public function, :func:`pronic_check`, that
returns ``True`` when its argument is a pronic number and ``False`` otherwise.
"""

import math

__all__ = ["pronic_check"]


def pronic_check(n):
    """Return ``True`` iff *n* is a pronic (oblong) number.

    A number ``x`` is pronic exactly when there exists a non-negative integer
    ``k`` such that ``x = k * (k + 1)``.  Equivalently, the discriminant of
    the quadratic equation ``k**2 + k - x = 0`` -- namely ``1 + 4x`` -- must
    be a perfect square and ``(-1 + sqrt(1 + 4x))`` must be a non-negative
    even integer.

    Edge-case behaviour
    -------------------
    * ``bool`` values are rejected (even though ``bool`` is a subclass of
      ``int`` in Python, ``True``/``False`` are not considered pronic).
    * Any value that is not an ``int`` (floats, strings, ``None``, lists,
      ...) returns ``False`` rather than raising.
    * Negative numbers return ``False`` -- the standard definition only
      considers products of *non-negative* consecutive integers.
    * ``0`` is considered pronic because ``0 = 0 * 1``.
    """
    # Booleans are technically ints in Python -- reject them up front so that
    # ``pronic_check(True)`` is ``False`` rather than ``True``.
    if isinstance(n, bool):
        return False

    # Only real integers can satisfy the pronic property; everything else
    # (float, str, None, list, ...) is silently treated as "not pronic".
    if not isinstance(n, int):
        return False

    # By convention, pronic numbers are products of *non-negative* integers.
    if n < 0:
        return False

    # Solve k**2 + k - n = 0 for the non-negative root:
    #     k = (-1 + sqrt(1 + 4n)) / 2
    #
    # ``math.isqrt`` works for arbitrarily large integers, so this is safe
    # for very large inputs (it does not suffer from float rounding errors).
    discriminant = 1 + 4 * n
    sqrt_disc = math.isqrt(discriminant)

    # Step 1: the discriminant itself must be a perfect square.
    if sqrt_disc * sqrt_disc != discriminant:
        return False

    # Step 2: ``-1 + sqrt_disc`` must be a non-negative even integer.
    numerator = sqrt_disc - 1
    if numerator < 0 or numerator % 2 != 0:
        return False

    k = numerator // 2
    # Defensive final check: ensure round-trip consistency.
    return k * (k + 1) == n