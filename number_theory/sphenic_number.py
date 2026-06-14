"""
Sphenic number utilities.

A sphenic number is a positive integer that is the product of three distinct
prime numbers. Equivalently, it is a positive integer that has exactly three
distinct prime factors, each with multiplicity exactly one. The smallest
sphenic number is 30 = 2 * 3 * 5.
"""


def sphenic_number(n):
    """Return True if ``n`` is a sphenic number, otherwise return False.

    A sphenic number is a positive integer that is the product of three
    distinct prime numbers. Therefore the number must satisfy:

        * it is a positive integer,
        * it has exactly three distinct prime factors,
        * each of those prime factors appears with multiplicity exactly one.

    Parameters
    ----------
    n : int
        The value to test.

    Returns
    -------
    bool
        True if ``n`` is a sphenic number, False otherwise. Non-integer
        inputs, booleans, and non-positive integers always return False.

    Examples
    --------
    >>> sphenic_number(30)
    True
    >>> sphenic_number(60)
    False
    >>> sphenic_number(1)
    False
    >>> sphenic_number(-30)
    False
    """
    # Reject anything that is not a positive integer. ``bool`` is a subclass
    # of ``int`` in Python, but treating True/False as numbers is almost
    # always a bug, so we filter them out explicitly.
    if not isinstance(n, int) or isinstance(n, bool):
        return False
    if n < 1:
        return False

    # Factorise ``n`` by trial division. We keep track of each distinct
    # prime divisor together with the multiplicity with which it appears.
    distinct_primes = set()
    multiplicities = []
    temp = n
    divisor = 2
    while divisor * divisor <= temp:
        if temp % divisor == 0:
            distinct_primes.add(divisor)
            count = 0
            while temp % divisor == 0:
                temp //= divisor
                count += 1
            multiplicities.append(count)
        divisor += 1

    # If a prime factor larger than sqrt(n) remains, it is prime by itself
    # and appears with multiplicity 1.
    if temp > 1:
        distinct_primes.add(temp)
        multiplicities.append(1)

    # A sphenic number has exactly three distinct prime factors, each of
    # which appears exactly once.
    return (
        len(distinct_primes) == 3
        and len(multiplicities) == 3
        and all(m == 1 for m in multiplicities)
    )