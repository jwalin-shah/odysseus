"""Niven predicate implementation.

A Niven number (also called a Harshad number) is a positive integer that is
divisible by the sum of its digits.  For example, 18 is a Niven number
because 1 + 8 = 9 and 18 % 9 == 0, while 19 is not because 1 + 9 = 10
and 19 % 10 == 1.
"""


def niven_predicate(n):
    """Return True if ``n`` is a Niven (Harshad) number, False otherwise.

    A Niven number is a *positive* integer that is divisible by the sum of
    its decimal digits.

    Parameters
    ----------
    n : int
        The number to test.

    Returns
    -------
    bool
        True if ``n`` is a Niven number, False otherwise.

    Notes
    -----
    Edge case handling:

    * Non-integer inputs (floats, strings, ``None``, etc.) return ``False``.
    * Booleans return ``False`` (although ``isinstance(True, int)`` is True
      in Python, booleans are conceptually not valid inputs for a number
      property test).
    * ``0`` returns ``False`` (it is not a positive integer and the
      digit-sum would be 0, causing division by zero).
    * Negative integers return ``False`` (the definition requires a
      positive integer).
    """
    # Reject anything that is not a real integer, and explicitly reject
    # booleans even though they are a subtype of ``int`` in Python.
    if not isinstance(n, int) or isinstance(n, bool):
        return False

    # Niven numbers are defined for positive integers only.
    if n <= 0:
        return False

    digit_sum = sum(int(digit) for digit in str(n))

    # The digit sum is always >= 1 for a positive integer, so this is safe.
    return n % digit_sum == 0


__all__ = ["niven_predicate"]