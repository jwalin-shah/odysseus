"""Moran number predicate.

A Moran number is a natural number n such that n divided by the sum of
its digits is a prime number. For example:
    - 18: 18 / (1+8) = 2  (prime)  -> Moran
    - 21: 21 / (2+1) = 7  (prime)  -> Moran
    - 27: 27 / (2+7) = 3  (prime)  -> Moran
    - 216: 216 / (2+1+6) = 24 (not prime) -> not Moran
"""


def _is_prime(n: int) -> bool:
    """Return True iff n is a prime number (n >= 2)."""
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    i = 3
    # Use i*i <= n to avoid floating point and overflow concerns for
    # the ranges we care about here.
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def is_moran(n: int) -> bool:
    """Return True if n is a Moran number.

    A Moran number is a natural number n such that n divided by the
    sum of its digits is a prime number. Equivalently, n % digit_sum(n)
    must be 0 and the quotient must be prime.

    Edge cases:
        - Non-integers, booleans, and values < 1 return False.
        - n = 0 returns False (digit sum is 0, quotient undefined).

    Examples:
        >>> is_moran(18)
        True
        >>> is_moran(21)
        True
        >>> is_moran(27)
        True
        >>> is_moran(216)
        False
        >>> is_moran(0)
        False
    """
    # Reject booleans (which are ints in Python), non-ints, and non-positive.
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        return False

    # Compute digit sum without converting to string.
    digit_sum = 0
    temp = n
    while temp > 0:
        digit_sum += temp % 10
        temp //= 10

    # If digit sum is 0 we would divide by zero; also impossible for n >= 1
    # unless we somehow have n=0 which is filtered above. Guard anyway.
    if digit_sum == 0:
        return False

    # n must be divisible by its digit sum for the quotient to be an integer.
    if n % digit_sum != 0:
        return False

    quotient = n // digit_sum
    return _is_prime(quotient)