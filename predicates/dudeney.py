"""Dudeney number predicate.

A Dudeney number is a positive integer that is a perfect cube such that
the sum of its decimal digits equals the cube root of the number.

The known Dudeney numbers in base 10 are:
    1      = 1^3   (1 = 1)
    512    = 8^3   (5+1+2 = 8)
    4913   = 17^3  (4+9+1+3 = 17)
    5832   = 18^3  (5+8+3+2 = 18)
    17576  = 26^3  (1+7+5+7+6 = 26)
    19683  = 27^3  (1+9+6+8+3 = 27)
"""

__all__ = ["is_dudeney"]


def is_dudeney(n):
    """Return True if ``n`` is a Dudeney number, False otherwise.

    The argument must be a positive integer. Any other input type or
    a value that is not a positive integer returns False.
    """
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        return False

    # Locate the integer cube root. Using ``** (1/3)`` on very large
    # numbers is subject to floating-point error, so we check the
    # rounding candidate plus its immediate neighbours.
    candidate = round(n ** (1.0 / 3.0))
    cube_root = None
    for c in (candidate - 1, candidate, candidate + 1):
        if c > 0 and c * c * c == n:
            cube_root = c
            break

    if cube_root is None:
        return False

    digit_sum = 0
    for ch in str(n):
        digit_sum += ord(ch) - 48  # ord('0') == 48, faster than int()

    return digit_sum == cube_root