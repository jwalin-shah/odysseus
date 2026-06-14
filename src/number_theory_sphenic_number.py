"""Sphenic number check.

A *sphenic number* is a positive integer that can be written as the
product of three **distinct** prime numbers.  Equivalently, it is a
positive integer with exactly three distinct prime factors, each of
which appears with multiplicity one.

The smallest sphenic number is 30 = 2 x 3 x 5.  Some other examples:

* 42  = 2 x 3 x  7
* 66  = 2 x 3 x 11
* 70  = 2 x 5 x  7
* 78  = 2 x 3 x 13
* 102 = 2 x 3 x 17

Numbers such as 60 (= 2^2 x 3 x 5), 210 (= 2 x 3 x 5 x 7) or
12 (= 2^2 x 3) are **not** sphenic because they either have a repeated
prime factor or contain more than three primes.
"""


def number_theory_sphenic_number(n):
    """Return ``True`` if ``n`` is a sphenic number, else ``False``.

    A number is sphenic exactly when it has three distinct prime
    factors, each appearing with exponent one in its prime
    factorisation.  The smallest sphenic number is 30, so any input
    below 30 cannot be sphenic.

    Parameters
    ----------
    n : int
        Candidate integer.

    Returns
    -------
    bool
        ``True`` when ``n`` is the product of three distinct primes,
        ``False`` otherwise (including when ``n`` is not an integer
        or is not a positive integer).
    """
    # Reject non-integers, booleans (which are ints in Python) and
    # numbers that are too small to be a product of three primes.
    if not isinstance(n, int) or isinstance(n, bool) or n < 2:
        return False

    distinct_primes = []
    value = n
    d = 2
    # Trial division up to sqrt(value).
    while d * d <= value:
        if value % d == 0:
            distinct_primes.append(d)
            value //= d
            # A repeated prime factor disqualifies ``n`` from being
            # sphenic: it would have fewer than three distinct primes.
            if value % d == 0:
                return False
        else:
            d += 1

    # Anything larger than 1 left over is itself a prime factor.
    if value > 1:
        distinct_primes.append(value)

    return len(distinct_primes) == 3