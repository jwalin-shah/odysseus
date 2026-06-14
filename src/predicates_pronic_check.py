"""Pronic (oblong) number predicate.

A *pronic* (or *oblong*) number is the product of two consecutive
non-negative integers:

    n = k * (k + 1)        for some integer k >= 0

The sequence of pronic numbers begins::

    0, 2, 6, 12, 20, 30, 42, 56, 72, 90, 110, ...

An equivalent algebraic characterisation is that ``n`` is pronic if and
only if ``4n + 1`` is a perfect square (specifically the square of an odd
integer).  This module exposes a small ``is_pronic`` predicate that
implements that test robustly, plus an alias matching the module name.
"""

from __future__ import annotations

import math
from typing import Any


def is_pronic(n: Any) -> bool:
    """Return ``True`` if ``n`` is a pronic (oblong) number.

    A value is considered pronic when it can be written as
    ``k * (k + 1)`` for some non-negative integer ``k``.

    Edge cases
    ----------
    * ``bool`` instances return ``False`` (booleans are technically a
      subclass of ``int`` but are not meaningful inputs here).
    * Non-``int`` values (floats, strings, ``None``, containers, ...)
      return ``False`` rather than raising.
    * Negative integers return ``False`` because ``k * (k + 1) >= 0`` for
      every integer ``k``.
    """
    # ``bool`` is a subclass of ``int``; reject it explicitly.
    if isinstance(n, bool):
        return False

    # Only plain integers are accepted.
    if not isinstance(n, int):
        return False

    # k * (k + 1) is non-negative for every integer k, so negatives are out.
    if n < 0:
        return False

    # 4n + 1 must be a perfect square for n to be pronic.
    discriminant = 4 * n + 1
    s = math.isqrt(discriminant)
    if s * s != discriminant:
        return False

    # The square root must be odd: if (2k + 1)^2 = 4n + 1 then k = (s - 1)/2.
    if s % 2 == 0:
        return False

    k = (s - 1) // 2
    return k * (k + 1) == n


# Convenience alias mirroring the module/file name.
predicates_pronic_check = is_pronic


__all__ = ["is_pronic", "predicates_pronic_check"]