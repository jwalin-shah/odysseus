"""Validation predicate for the Kish-Lengyel prime conjuncture.

This module provides a predicate function that validates whether a given
number satisfies a specific prime-related conjuncture property used in
the Odysseus project's validation framework.
"""


def validation_predicates_kish_lengyel_prime_conjuncture_predicate(n):
    """Check if n satisfies the Kish-Lengyel prime conjuncture predicate.

    The predicate determines whether the given integer n is a prime
    number, which is the core property validated by the Kish-Lengyel
    prime conjuncture checker.

    Args:
        n: The value to validate. Integer values are expected for a
            meaningful result; non-integer inputs return False.

    Returns:
        True if n is a prime number, False otherwise (including for
        non-integer inputs, values less than 2, and composite numbers).
    """
    # Type check: only integer values are considered for primality here.
    if not isinstance(n, int) or isinstance(n, bool):
        return False

    # By definition, primes are integers greater than 1.
    if n < 2:
        return False

    # 2 is the only even prime.
    if n == 2:
        return True

    # Any other even number is composite.
    if n % 2 == 0:
        return False

    # Check odd divisors up to sqrt(n). Since n is odd and >= 3,
    # we only need to test odd divisors, incrementing by 2.
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2

    return True