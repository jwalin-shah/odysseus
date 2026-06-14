"""
Pytest tests for ``legendre_factorial_prime_exponent``.

These tests cover basic correctness on small values that can be verified by
hand, several larger values verified against known results, and the error
handling for invalid input.
"""

from __future__ import annotations

import math
import os
import sys

import pytest

# Make the src/ directory importable when tests are run from the project root.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_PROJECT_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from src_number_theory_legendre_factorial_prime_exponent import (  # noqa: E402
    legendre_factorial_prime_exponent,
)


# ---------------------------------------------------------------------------
# Helper: brute-force reference implementation
# ---------------------------------------------------------------------------
def _bruteforce_exponent(n: int, p: int) -> int:
    """Compute the exponent of ``p`` in ``n!`` by factoring the factorial."""
    if n < 2:
        return 0
    result = 0
    fact = math.factorial(n)
    while fact % p == 0:
        result += 1
        fact //= p
    return result


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------
def test_0_factorial_has_no_prime_factors():
    assert legendre_factorial_prime_exponent(0, 2) == 0
    assert legendre_factorial_prime_exponent(0, 3) == 0
    assert legendre_factorial_prime_exponent(0, 5) == 0


def test_1_factorial_has_no_prime_factors():
    assert legendre_factorial_prime_exponent(1, 2) == 0
    assert legendre_factorial_prime_exponent(1, 7) == 0


def test_5_factorial_prime_breakdown():
    # 5! = 120 = 2^3 * 3 * 5
    assert legendre_factorial_prime_exponent(5, 2) == 3
    assert legendre_factorial_prime_exponent(5, 3) == 1
    assert legendre_factorial_prime_exponent(5, 5) == 1


def test_5_factorial_uninvolved_prime():
    # 7 does not divide 5!
    assert legendre_factorial_prime_exponent(5, 7) == 0


def test_10_factorial_2():
    # 10! exponent of 2 = floor(10/2) + floor(10/4) + floor(10/8) = 5+2+1 = 8
    assert legendre_factorial_prime_exponent(10, 2) == 8


def test_10_factorial_3():
    # floor(10/3) + floor(10/9) = 3 + 1 = 4
    assert legendre_factorial_prime_exponent(10, 3) == 4


def test_10_factorial_5():
    # floor(10/5) = 2
    assert legendre_factorial_prime_exponent(10, 5) == 2


def test_10_factorial_7():
    # floor(10/7) = 1
    assert legendre_factorial_prime_exponent(10, 7) == 1


def test_10_factorial_11():
    # 11 > 10, so 11 does not divide 10!
    assert legendre_factorial_prime_exponent(10, 11) == 0


def test_25_factorial_2():
    # 12 + 6 + 3 + 1 = 22
    assert legendre_factorial_prime_exponent(25, 2) == 22


def test_25_factorial_5():
    # floor(25/5) + floor(25/25) = 5 + 1 = 6
    assert legendre_factorial_prime_exponent(25, 5) == 6


def test_100_factorial_2():
    # 50 + 25 + 12 + 6 + 3 + 1 = 97
    assert legendre_factorial_prime_exponent(100, 2) == 97


def test_100_factorial_5():
    # 20 + 4 = 24
    assert legendre_factorial_prime_exponent(100, 5) == 24


def test_100_factorial_97():
    # 97 is prime, 97 <= 100 < 97*97
    assert legendre_factorial_prime_exponent(100, 97) == 1


# ---------------------------------------------------------------------------
# Cross-check against a brute-force implementation
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 30, 50, 100])
@pytest.mark.parametrize("p", [2, 3, 5, 7, 11, 13, 17, 19, 23, 29])
def test_matches_bruteforce(n, p):
    assert legendre_factorial_prime_exponent(n, p) == _bruteforce_exponent(n, p)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
def test_negative_n_raises_value_error():
    with pytest.raises(ValueError):
        legendre_factorial_prime_exponent(-1, 2)
    with pytest.raises(ValueError):
        legendre_factorial_prime_exponent(-100, 3)


def test_p_less_than_2_raises_value_error():
    with pytest.raises(ValueError):
        legendre_factorial_prime_exponent(5, 1)
    with pytest.raises(ValueError):
        legendre_factorial_prime_exponent(5, 0)
    with pytest.raises(ValueError):
        legendre_factorial_prime_exponent(5, -3)


def test_non_integer_n_raises_type_error():
    with pytest.raises(TypeError):
        legendre_factorial_prime_exponent(5.0, 2)
    with pytest.raises(TypeError):
        legendre_factorial_prime_exponent("5", 2)
    with pytest.raises(TypeError):
        legendre_factorial_prime_exponent(None, 2)


def test_non_integer_p_raises_type_error():
    with pytest.raises(TypeError):
        legendre_factorial_prime_exponent(5, 2.0)
    with pytest.raises(TypeError):
        legendre_factorial_prime_exponent(5, "2")


# ---------------------------------------------------------------------------
# Property checks
# ---------------------------------------------------------------------------
def test_n_factorial_exponent_of_n_minus_1_is_at_least_1():
    # (n-1)! is divisible by every prime less than n.
    for n in [2, 3, 4, 5, 6, 7, 8, 9, 10]:
        for p in range(2, n):
            assert legendre_factorial_prime_exponent(n - 1, p) >= 1, (
                f"prime {p} should divide {n - 1}!"
            )


def test_larger_n_gives_at_least_as_large_exponent():
    for p in [2, 3, 5, 7]:
        for a, b in [(3, 5), (5, 10), (10, 20), (20, 50)]:
            assert (
                legendre_factorial_prime_exponent(b, p)
                >= legendre_factorial_prime_exponent(a, p)
            )