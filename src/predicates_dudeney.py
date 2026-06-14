"""Dudeney number predicate.

A Dudeney number is a positive integer that is a perfect cube
such that the sum of its decimal digits equals the cube root of
the number. Named after the English author Henry Dudeney.

The sequence of Dudeney numbers begins:
    1, 512, 4913, 5832, 17576, 19683, 54872, 421875, ...
"""


def is_dudeney(n):
    """Return True if n is a Dudeney number, False otherwise.

    A Dudeney number is a positive integer that is a perfect cube
    whose sum of decimal digits equals its cube root.

    Parameters
    ----------
    n : int
        The number to test.

    Returns
    -------
    bool
        True if n is a Dudeney number, False otherwise.

    Examples
    --------
    >>> is_dudeney(1)
    True
    >>> is_dudeney(512)
    True
    >>> is_dudeney(8)
    False
    """
    # Reject non-integers, booleans, and non-positive numbers.
    if not isinstance(n, int) or isinstance(n, bool):
        return False
    if n < 1:
        return False

    # Approximate the cube root using floating-point math, then
    # verify by trying a few nearby integer candidates. This
    # guards against floating-point rounding errors (e.g. when
    # n ** (1/3) returns 26.9999... instead of 27).
    approx = round(n ** (1.0 / 3.0))

    for candidate in range(max(1, approx - 2), approx + 3):
        if candidate ** 3 == n:
            digit_sum = sum(int(d) for d in str(n))
            return digit_sum == candidate

    return False