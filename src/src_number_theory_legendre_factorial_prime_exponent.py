"""
Implementation of Legendre's formula for the exponent of a prime p
in the prime factorization of n!.

Legendre's formula:
    e_p(n!) = floor(n / p) + floor(n / p^2) + floor(n / p^3) + ...

This sum continues while p^k <= n.
"""

from __future__ import annotations


def legendre_factorial_prime_exponent(n: int, p: int) -> int:
    """
    Compute the exponent of a prime ``p`` in the prime factorization of ``n!``.

    Parameters
    ----------
    n : int
        A non-negative integer. The argument of the factorial.
    p : int
        A prime number (p >= 2) whose exponent in n! is sought.

    Returns
    -------
    int
        The exponent of ``p`` in ``n!`` (i.e. the largest integer ``e`` such
        that ``p**e`` divides ``n!``).

    Raises
    ------
    TypeError
        If either ``n`` or ``p`` is not an integer.
    ValueError
        If ``n`` is negative, or if ``p`` is not at least 2.

    Examples
    --------
    >>> legendre_factorial_prime_exponent(5, 2)
    3
    >>> legendre_factorial_prime_exponent(5, 3)
    1
    >>> legendre_factorial_prime_exponent(10, 2)
    8
    >>> legendre_factorial_prime_exponent(10, 5)
    2
    """
    # Input validation -------------------------------------------------------
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("n must be an integer")
    if not isinstance(p, int) or isinstance(p, bool):
        raise TypeError("p must be an integer")

    if n < 0:
        raise ValueError("n must be non-negative")
    if p < 2:
        raise ValueError("p must be a prime (p >= 2)")

    # Edge case: 0! = 1 and 1! = 1, neither contains any prime factor.
    if n < 2:
        return 0

    # Legendre's formula: sum floor(n / p^k) for k = 1, 2, ... while p^k <= n
    exponent = 0
    pk = p
    while pk <= n:
        exponent += n // pk
        # Guard against runaway growth (purely defensive; Python ints are
        # unbounded so this is just an optimisation for very large n).
        if pk > n // p:
            break
        pk *= p

    return exponent


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    # Quick sanity check
    for n in [0, 1, 5, 10, 25, 100]:
        for p in [2, 3, 5, 7, 11, 13]:
            print(f"e_{p}({n}!) = {legendre_factorial_prime_exponent(n, p)}")