"""Moran number predicate.

A Moran number is a positive integer N such that N divided by the sum of the
digits of N is a prime number. Equivalently, N = p * s(N) where s(N) is the
digit sum of N and p is prime.
"""


def _is_prime(n: int) -> bool:
    """Return True iff n is a prime number."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def _digit_sum(n: int) -> int:
    """Return the sum of the decimal digits of n (n >= 0)."""
    total = 0
    for ch in str(n):
        total += int(ch)
    return total


def predicates_moran_number(n: int) -> bool:
    """Return True if ``n`` is a Moran number, False otherwise.

    A number is Moran if dividing it by the sum of its digits yields a prime.
    Non-positive integers, booleans, and non-integers return False.
    """
    # Reject booleans (which are ints in Python) and any non-integer type.
    if isinstance(n, bool) or not isinstance(n, int):
        return False
    if n < 1:
        return False

    s = _digit_sum(n)
    if s == 0:
        # Only happens for n == 0, already filtered above, but be safe.
        return False
    if n % s != 0:
        return False
    return _is_prime(n // s)