"""Munchausen number checker.

A Munchausen number is a natural number equal to the sum of its digits
raised to the power of each digit itself. By convention used here, 0^0 = 0
and 0 itself is not considered a Munchausen number (the trivial case is
excluded).

The only known Munchausen numbers in base 10 are 1 and 3435.
"""


def _digit_power(d):
    """Compute d ** d, treating 0 ** 0 as 0 (the standard Munchausen convention)."""
    if d == 0:
        return 0
    return d ** d


def munchausen_check(n):
    """Return True if ``n`` is a Munchausen number, False otherwise.

    A Munchausen number equals the sum of each of its decimal digits
    raised to the power of that digit. For example::

        3435 = 3**3 + 4**4 + 3**3 + 5**5 = 27 + 256 + 27 + 3125 = 3435

    Args:
        n: The value to test. Non-integers, booleans, negative numbers
            and zero all return ``False``.

    Returns:
        bool: ``True`` if ``n`` is a Munchausen number, ``False`` otherwise.
    """
    # Reject anything that isn't a "real" non-negative integer.
    if not isinstance(n, int) or isinstance(n, bool):
        return False
    if n < 0 or n == 0:
        return False

    total = sum(_digit_power(int(c)) for c in str(n))
    return total == n