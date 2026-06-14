"""Legendre's formula for the exponent of a prime in n!.

Given a non-negative integer n and a prime p, computes the largest integer
e such that p**e divides n! (i.e. the exponent of p in the prime
factorization of n!).

Legendre's formula:

    e = floor(n / p) + floor(n / p**2) + floor(n / p**3) + ...

The sum is finite because once p**k > n, every subsequent term is zero.
"""


def legendre_factorial_prime_exponent(n, p):
    """Return the exponent of prime ``p`` in ``n!`` using Legendre's formula.

    Parameters
    ----------
    n : int
        A non-negative integer.
    p : int
        A prime number (>= 2). The function does not verify that ``p`` is
        actually prime, but it requires ``p >= 2``.

    Returns
    -------
    int
        The exponent of ``p`` in the prime factorization of ``n!``.

    Raises
    ------
    TypeError
        If ``n`` or ``p`` is not an integer.
    ValueError
        If ``n`` is negative or ``p`` is less than 2.
    """
    # Type / value validation. We deliberately keep the checks minimal so the
    # function remains fast and predictable.
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("n must be an integer")
    if not isinstance(p, int) or isinstance(p, bool):
        raise TypeError("p must be an integer")
    if n < 0:
        raise ValueError("n must be non-negative")
    if p < 2:
        raise ValueError("p must be an integer >= 2")

    exponent = 0
    power = p
    # While p**k <= n, accumulate floor(n / p**k).
    # Using an iterative multiplication (power *= p) avoids recomputing
    # p**k from scratch and is robust for moderately large inputs.
    while power <= n:
        exponent += n // power
        # Guard against the (impossible, given p >= 2) overflow on power.
        if power > n // p:
            break
        power *= p
    return exponent


# Convenience alias used by some callers / older tests.
def prime_factorial_exponent(n, p):
    """Alias for :func:`legendre_factorial_prime_exponent`."""
    return legendre_factorial_prime_exponent(n, p)