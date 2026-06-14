import pytest
from math import gcd
from carmichael_lambda import carmichael_lambda


# Known values for the Carmichael lambda function
KNOWN_VALUES = [
    (1, 1),
    (2, 1),
    (3, 2),
    (4, 2),
    (5, 4),
    (6, 2),
    (7, 6),
    (8, 2),
    (9, 6),
    (10, 4),
    (11, 10),
    (12, 2),
    (13, 12),
    (14, 6),
    (15, 4),
    (16, 4),
    (17, 16),
    (18, 6),
    (19, 18),
    (20, 4),
    (21, 6),
    (22, 10),
    (23, 22),
    (24, 2),
    (25, 20),
    (26, 12),
    (27, 18),
    (28, 6),
    (29, 28),
    (30, 4),
    (31, 30),
    (32, 8),
    (33, 10),
    (34, 16),
    (35, 12),
    (36, 6),
    (37, 36),
    (38, 18),
    (39, 12),
    (40, 4),
    (41, 40),
    (42, 6),
    (43, 42),
    (44, 10),
    (45, 12),
    (46, 22),
    (47, 46),
    (48, 4),
    (49, 42),
    (50, 20),
    (97, 96),
    (100, 20),
    (1000, 100),
    (1008, 12),
    (2465, 112),
    (41041, 120),
    (561, 80),
]


@pytest.mark.parametrize("n,expected", KNOWN_VALUES)
def test_known_values(n, expected):
    assert carmichael_lambda(n) == expected


def test_lambda_1():
    assert carmichael_lambda(1) == 1


def test_prime_lambda():
    # For a prime p, lambda(p) = p - 1
    for p in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]:
        assert carmichael_lambda(p) == p - 1


def test_prime_power_lambda():
    # For odd prime p and k >= 1: lambda(p^k) = p^(k-1) * (p-1)
    assert carmichael_lambda(3 ** 2) == 3 * 2
    assert carmichael_lambda(3 ** 3) == 9 * 2
    assert carmichael_lambda(5 ** 2) == 5 * 4
    assert carmichael_lambda(5 ** 3) == 25 * 4
    assert carmichael_lambda(7 ** 2) == 7 * 6


def test_power_of_2_lambda():
    # Special handling for powers of 2
    assert carmichael_lambda(2) == 1
    assert carmichael_lambda(4) == 2
    assert carmichael_lambda(8) == 2
    assert carmichael_lambda(16) == 4
    assert carmichael_lambda(32) == 8
    assert carmichael_lambda(64) == 16
    assert carmichael_lambda(128) == 32
    assert carmichael_lambda(256) == 64


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 21, 26, 28, 35, 36, 100, 561, 1008, 2465, 41041])
def test_universal_exponent_property_parametrized(n):
    # The defining property: for all a coprime to n, a^lambda(n) ≡ 1 (mod n)
    lam = carmichael_lambda(n)
    for a in range(1, n):
        if gcd(a, n) == 1:
            assert pow(a, lam, n) == 1


def test_universal_exponent_property():
    # Single comprehensive check on a moderately sized n
    n = 97 * 101 * 103  # product of three distinct primes
    lam = carmichael_lambda(n)
    for a in range(1, 50):
        if gcd(a, n) == 1:
            assert pow(a, lam, n) == 1


def test_carmichael_numbers():
    # Carmichael numbers are composite n such that a^(n-1) ≡ 1 (mod n) for all a coprime to n.
    # This is equivalent to lambda(n) | (n-1).
    carmichael_nums = [561, 1105, 1729, 2465, 2821, 6601, 8911, 10585, 15841, 29341, 41041, 46657, 52633, 62745, 63973, 75361]
    for n in carmichael_nums:
        lam = carmichael_lambda(n)
        assert (n - 1) % lam == 0, f"lambda({n})={lam} does not divide n-1={n-1}"


def test_lambda_divides_euler_phi():
    # For all n, lambda(n) divides phi(n).
    def euler_phi(n):
        result = n
        p = 2
        nn = n
        while p * p <= nn:
            if nn % p == 0:
                while nn % p == 0:
                    nn //= p
                result -= result // p
            p += 1
        if nn > 1:
            result -= result // nn
        return result

    for n in range(1, 200):
        phi = euler_phi(n)
        lam = carmichael_lambda(n)
        assert phi % lam == 0, f"phi({n})={phi} is not a multiple of lambda({n})={lam}"


def test_invalid_input():
    with pytest.raises(ValueError):
        carmichael_lambda(0)
    with pytest.raises(ValueError):
        carmichael_lambda(-5)
    with pytest.raises(ValueError):
        carmichael_lambda(1.5)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        carmichael_lambda("100")  # type: ignore[arg-type]