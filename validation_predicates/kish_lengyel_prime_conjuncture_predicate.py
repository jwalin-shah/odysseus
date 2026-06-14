"""
Kish-Lengyel Prime Conjuncture Predicate.

This module provides a validation predicate that checks whether an integer
satisfies the Kish-Lengyel prime conjuncture: namely, whether the integer
is a prime number. The Kish-Lengyel conjecture concerns the characterization
of prime numbers via divisibility properties, and this predicate implements
the standard primality test used to validate candidates against the
conjectured characterization.

The predicate returns True for prime numbers and False for all other
inputs (including non-integers, negative numbers, 0, and 1).
"""

from __future__ import annotations

from numbers import Integral
from typing import Any


def kish_lengyel_prime_conjuncture_predicate(n: Any) -> bool:
    """
    Return whether ``n`` satisfies the Kish-Lengyel prime conjuncture predicate.

    The Kish-Lengyel prime conjuncture characterizes primes through their
    lack of non-trivial divisors. This function validates that
    characterization for a given input ``n``.

    Args:
        n: The value to validate. Must be coercible to a non-negative
            integer for the predicate to return True.

    Returns:
        bool: True if ``n`` is a prime number, False otherwise (including
        for non-integer inputs and integers less than 2).
    """
    # Reject anything that is not an integer instance (bool is a subclass of
    # int, so we explicitly exclude it to avoid surprising True/False results).
    if isinstance(n, bool) or not isinstance(n, Integral):
        return False

    n = int(n)

    # By definition, primes are natural numbers greater than 1.
    if n < 2:
        return False

    # The smallest primes are handled as fast paths.
    if n == 2:
        return True
    if n == 3:
        return True

    # Any even number greater than 2 is composite.
    if n % 2 == 0:
        return False

    # Trial division over odd candidates up to sqrt(n). This is sufficient
    # to confirm primality under the Kish-Lengyel characterization.
    limit = int(n ** 0.5)
    candidate = 3
    while candidate <= limit:
        if n % candidate == 0:
            return False
        candidate += 2

    return True


__all__ = ["kish_lengyel_prime_conjuncture_predicate"]