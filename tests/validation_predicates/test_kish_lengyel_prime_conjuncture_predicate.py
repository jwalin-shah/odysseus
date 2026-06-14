"""
Tests for the Kish-Lengyel prime conjuncture predicate.

These tests exercise the predicate over known primes, known composites,
boundary values, negative inputs, and non-integer inputs to ensure the
implementation is correct and robust.
"""

import math

import pytest

from validation_predicates.kish_lengyel_prime_conjuncture_predicate import (
    kish_lengyel_prime_conjuncture_predicate,
)


# ---------------------------------------------------------------------------
# Known primes up to 100
# ---------------------------------------------------------------------------
KNOWN_PRIMES = [
    2, 3, 5, 7, 11, 13, 17, 19, 23, 29,
    31, 37, 41, 43, 47, 53, 59, 61, 67, 71,
    73, 79, 83, 89, 97,
]

# ---------------------------------------------------------------------------
# Known composites and other non-prime integers up to 100
# ---------------------------------------------------------------------------
KNOWN_NON_PRIMES = [
    -100, -10, -3, -2, -1, 0, 1,
    4, 6, 8, 9, 10, 12, 14, 15, 16, 18, 20,
    21, 22, 24, 25, 26, 27, 28, 30, 32, 33,
    34, 35, 36, 38, 39, 40, 42, 44, 45, 46,
    48, 49, 50, 51, 52, 54, 55, 56, 57, 58,
    60, 62, 63, 64, 65, 66, 68, 69, 70, 72,
    74, 75, 76, 77, 78, 80, 81, 82, 84, 85,
    86, 87, 88, 90, 91, 92, 93, 94, 95, 96,
    98, 99, 100,
]


def test_small_primes_are_predicate_true():
    """Every known prime under 100 must be accepted by the predicate."""
    for prime in KNOWN_PRIMES:
        assert kish_lengyel_prime_conjuncture_predicate(prime) is True, (
            f"Expected {prime} to satisfy the Kish-Lengyel prime predicate"
        )


def test_small_non_primes_are_predicate_false():
    """Every known non-prime under 100 must be rejected by the predicate."""
    for non_prime in KNOWN_NON_PRIMES:
        assert kish_lengyel_prime_conjuncture_predicate(non_prime) is False, (
            f"Expected {non_prime} to fail the Kish-Lengyel prime predicate"
        )


def test_boundary_values():
    """Boundary inputs 0, 1, 2, and 3 must be handled correctly."""
    assert kish_lengyel_prime_conjuncture_predicate(0) is False
    assert kish_lengyel_prime_conjuncture_predicate(1) is False
    assert kish_lengyel_prime_conjuncture_predicate(2) is True
    assert kish_lengyel_prime_conjuncture_predicate(3) is True


def test_negative_numbers_are_not_prime():
    """Negative integers must always be rejected."""
    for value in [-1, -2, -3, -7, -11, -97, -1000]:
        assert kish_lengyel_prime_conjuncture_predicate(value) is False


def test_even_numbers_above_two_are_not_prime():
    """All even integers greater than 2 must be rejected."""
    for value in [4, 6, 8, 10, 100, 1000, 1_000_000]:
        assert kish_lengyel_prime_conjuncture_predicate(value) is False


def test_larger_primes():
    """Larger known primes must be accepted by the predicate."""
    larger_primes = [101, 103, 211, 307, 401, 503, 701, 991, 1009, 7919]
    for prime in larger_primes:
        assert kish_lengyel_prime_conjuncture_predicate(prime) is True, (
            f"Expected {prime} to be recognized as prime"
        )


def test_larger_composites():
    """Larger known composites must be rejected by the predicate."""
    larger_composites = [102, 104, 210, 308, 400, 504, 700, 990, 1000, 7917]
    for composite in larger_composites:
        assert kish_lengyel_prime_conjuncture_predicate(composite) is False, (
            f"Expected {composite} to be recognized as composite"
        )


def test_perfect_squares_of_primes():
    """Squares of primes (e.g. 49 = 7*7) must be rejected."""
    for prime in [2, 3, 5, 7, 11, 13, 17, 19, 23]:
        square = prime * prime
        assert kish_lengyel_prime_conjuncture_predicate(square) is False


def test_product_of_two_distinct_primes():
    """Products of two distinct primes must be rejected."""
    products = [2 * 3, 3 * 5, 5 * 7, 7 * 11, 11 * 13, 13 * 17, 19 * 23, 29 * 31]
    for product in products:
        assert kish_lengyel_prime_conjuncture_predicate(product) is False


def test_very_large_prime():
    """A known large prime (1,000,003) must be accepted."""
    # 1000003 is prime
    assert kish_lengyel_prime_conjuncture_predicate(1_000_003) is True


def test_very_large_composite():
    """A known large composite must be rejected."""
    # 1000005 = 3 * 5 * 66667
    assert kish_lengyel_prime_conjuncture_predicate(1_000_005) is False


def test_non_integer_inputs_are_rejected():
    """Non-integer inputs must be rejected by the predicate."""
    invalid_inputs = [
        2.0,           # float equal to a prime
        3.5,           # non-integer float
        "7",           # string that looks like a prime
        "prime",       # arbitrary string
        None,          # NoneType
        [2, 3],        # list
        (5,),          # tuple
        {7: "seven"},  # dict
        complex(3, 0), # complex with no imaginary part
    ]
    for value in invalid_inputs:
        assert kish_lengyel_prime_conjuncture_predicate(value) is False, (
            f"Expected {value!r} (type {type(value).__name__}) to be rejected"
        )


def test_boolean_inputs_are_rejected():
    """Booleans are integer-like but must be rejected to avoid ambiguity."""
    assert kish_lengyel_prime_conjuncture_predicate(True) is False
    assert kish_lengyel_prime_conjuncture_predicate(False) is False


@pytest.mark.parametrize("value", KNOWN_PRIMES)
def test_parametrized_known_primes(value: int):
    """Parametrized check for every known prime under 100."""
    assert kish_lengyel_prime_conjuncture_predicate(value) is True


@pytest.mark.parametrize("value", KNOWN_NON_PRIMES)
def test_parametrized_known_non_primes(value: int):
    """Parametrized check for every known non-prime under 100."""
    assert kish_lengyel_prime_conjuncture_predicate(value) is False


def test_predicate_matches_mathematical_primality_definition():
    """
    For the range [0, 200], the predicate must agree with the mathematical
    definition of primality (exactly the integers that have no positive
    divisor other than 1 and themselves).
    """
    def is_prime_math(n: int) -> bool:
        if n < 2:
            return False
        if n == 2:
            return True
        if n % 2 == 0:
            return False
        for i in range(3, int(math.isqrt(n)) + 1, 2):
            if n % i == 0:
                return False
        return True

    for n in range(0, 201):
        assert kish_lengyel_prime_conjuncture_predicate(n) is is_prime_math(n), (
            f"Disagreement at n={n}"
        )