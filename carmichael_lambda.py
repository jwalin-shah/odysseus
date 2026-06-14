from math import gcd


def _lcm(a, b):
    """Compute the least common multiple of a and b."""
    if a == 0 or b == 0:
        return 0
    return a * b // gcd(a, b)


def _factorize(n):
    """Return the prime factorization of n as a list of (prime, exponent) pairs."""
    factors = []
    d = 2
    while d * d <= n:
        if n % d == 0:
            k = 0
            while n % d == 0:
                n //= d
                k += 1
            factors.append((d, k))
        d += 1
    if n > 1:
        factors.append((n, 1))
    return factors


def carmichael_lambda(n):
    """Calculate the Carmichael function lambda(n).

    The Carmichael function lambda(n) is the smallest positive integer m
    such that a^m == 1 (mod n) for every integer a that is coprime to n.

    It is also called the reduced totient function or the universal exponent.

    Parameters
    ----------
    n : int
        A positive integer.

    Returns
    -------
    int
        The Carmichael lambda of n.

    Raises
    ------
    ValueError
        If n is not a positive integer.

    Examples
    --------
    >>> carmichael_lambda(1)
    1
    >>> carmichael_lambda(8)
    2
    >>> carmichael_lambda(561)
    80
    """
    if not isinstance(n, int) or n < 1:
        raise ValueError("n must be a positive integer")

    if n == 1:
        return 1

    factors = _factorize(n)
    result = 1
    for p, k in factors:
        if p == 2:
            if k == 1:
                lam_pk = 1
            elif k == 2:
                lam_pk = 2
            else:
                lam_pk = 2 ** (k - 2)
        else:
            lam_pk = (p ** (k - 1)) * (p - 1)
        result = _lcm(result, lam_pk)
    return result