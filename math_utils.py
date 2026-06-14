def gcd(a, b):
    """Compute the greatest common divisor using the Euclidean algorithm."""
    a, b = abs(a), abs(b)
    while b:
        a, b = b, a % b
    return a


def lcm(a, b):
    """Compute the least common multiple."""
    if a == 0 or b == 0:
        return 0
    return abs(a * b) // gcd(a, b)


def is_prime(n):
    """Miller-Rabin primality test, deterministic for n < 3.3e24."""
    if n < 2:
        return False
    # Quick check using small primes
    small_primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for p in small_primes:
        if n == p:
            return True
        if n % p == 0:
            return False
    # Write n - 1 as 2^r * d with d odd
    d = n - 1
    r = 0
    while d % 2 == 0:
        d //= 2
        r += 1
    # Deterministic witnesses for n < 3,317,044,064,679,887,385,961,981
    for a in small_primes:
        if a >= n:
            continue
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def prime_factors(n):
    """Return a sorted list of prime factors of n (with multiplicity)."""
    if n == 0:
        return []
    n = abs(n)
    if n == 1:
        return []
    factors = []
    # Factor out 2s
    while n % 2 == 0:
        factors.append(2)
        n //= 2
    # Factor out odd primes
    p = 3
    while p * p <= n:
        while n % p == 0:
            factors.append(p)
            n //= p
        p += 2
    if n > 1:
        factors.append(n)
    return factors


def power(base, exp, mod=None):
    """Fast exponentiation. If mod is given, computes (base ** exp) % mod."""
    if exp < 0:
        raise ValueError("exp must be non-negative")
    if mod is not None:
        return pow(base, exp, mod)
    result = 1
    base = base
    exp = int(exp)
    while exp > 0:
        if exp & 1:
            result *= base
        base *= base
        exp >>= 1
    return result


def combinations(n, k):
    """Compute nCk (binomial coefficient) without overflow via iterative reduction."""
    if k < 0 or k > n:
        return 0
    if k == 0 or k == n:
        return 1
    k = min(k, n - k)
    result = 1
    for i in range(1, k + 1):
        result = result * (n - k + i) // i
    return result


def permutations(n, k):
    """Compute nPk = n! / (n - k)!."""
    if k < 0 or k > n:
        return 0
    result = 1
    for i in range(k):
        result *= (n - i)
    return result