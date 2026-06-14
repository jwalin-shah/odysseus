"""Tests for :func:`number_theory_sphenic_number`."""

import pytest

from src.number_theory_sphenic_number import number_theory_sphenic_number


# ---------------------------------------------------------------------------
# Positive cases: known sphenic numbers
# ---------------------------------------------------------------------------

SPHENIC_NUMBERS = [
    30,    # 2  * 3  *  5
    42,    # 2  * 3  *  7
    66,    # 2  * 3  * 11
    70,    # 2  * 5  *  7
    78,    # 2  * 3  * 13
    102,   # 2  * 3  * 17
    105,   # 3  * 5  *  7
    110,   # 2  * 5  * 11
    114,   # 2  * 3  * 19
    130,   # 2  * 5  * 13
    138,   # 2  * 3  * 23
    154,   # 2  * 7  * 11
    165,   # 3  * 5  * 11
    170,   # 2  * 5  * 17
    174,   # 2  * 3  * 29
    182,   # 2  * 7  * 13
    186,   # 2  * 3  * 31
    190,   # 2  * 5  * 19
    195,   # 3  * 5  * 13
    222,   # 2  * 3  * 37
    230,   # 2  * 5  * 23
]


@pytest.mark.parametrize("n", SPHENIC_NUMBERS)
def test_is_sphenic(n):
    """Known sphenic numbers must be recognised as sphenic."""
    assert number_theory_sphenic_number(n) is True


# ---------------------------------------------------------------------------
# Negative cases: numbers that are NOT sphenic
# ---------------------------------------------------------------------------


def test_smallest_sphenic():
    """30 is the smallest sphenic number."""
    assert number_theory_sphenic_number(30) is True


@pytest.mark.parametrize(
    "n",
    [
        1,       # unit
        0,       # zero
        -1,      # negative
        -30,     # negative
        2,       # prime
        3,       # prime
        5,       # prime
        29,      # prime
        97,      # prime
        4,       # 2^2  - repeated prime
        8,       # 2^3  - repeated prime
        12,      # 2^2 * 3   - repeated prime
        18,      # 2   * 3^2 - repeated prime
        20,      # 2^2 * 5   - repeated prime
        60,      # 2^2 * 3 * 5 - repeated prime
        6,       # 2 * 3  - only two primes
        10,      # 2 * 5  - only two primes
        14,      # 2 * 7  - only two primes
        15,      # 3 * 5  - only two primes
        210,     # 2 * 3 * 5 * 7  - four distinct primes
        2310,    # 2 * 3 * 5 * 7 * 11 - five distinct primes
        100,     # 2^2 * 5^2 - squares of primes
        36,      # 6^2 = 2^2 * 3^2 - repeated primes
    ],
)
def test_is_not_sphenic(n):
    """Numbers that are not the product of three distinct primes."""
    assert number_theory_sphenic_number(n) is False


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_zero_is_not_sphenic():
    assert number_theory_sphenic_number(0) is False


def test_one_is_not_sphenic():
    assert number_theory_sphenic_number(1) is False


def test_negative_numbers_are_not_sphenic():
    assert number_theory_sphenic_number(-30) is False
    assert number_theory_sphenic_number(-42) is False


def test_non_integer_inputs_are_not_sphenic():
    assert number_theory_sphenic_number(30.0) is False
    assert number_theory_sphenic_number("30") is False
    assert number_theory_sphenic_number(None) is False
    assert number_theory_sphenic_number([30]) is False
    assert number_theory_sphenic_number((30,)) is False


def test_boolean_inputs_are_not_sphenic():
    """Booleans are a subclass of int in Python and must be rejected."""
    assert number_theory_sphenic_number(True) is False
    assert number_theory_sphenic_number(False) is False


def test_large_sphenic_number():
    """Sphenic numbers should be recognised even when they are large."""
    # 1001 = 7 * 11 * 13
    assert number_theory_sphenic_number(1001) is True
    # 2 * 3 * 5 * 7 * 11 = 2310 is not sphenic (five primes)
    assert number_theory_sphenic_number(2310) is False


def test_two_distinct_primes_is_not_sphenic():
    """Semi-primes (product of exactly two primes) are not sphenic."""
    semi_primes = (6, 10, 14, 15, 21, 22, 26, 33, 34, 35, 38, 39)
    for n in semi_primes:
        assert number_theory_sphenic_number(n) is False, (
            f"{n} is a semi-prime and should not be sphenic"
        )


def test_repeated_prime_factor_is_not_sphenic():
    """A repeated prime factor disqualifies the number from being sphenic."""
    repeated = (4, 8, 9, 12, 16, 18, 20, 24, 25, 27, 36, 48, 49, 50, 60)
    for n in repeated:
        assert number_theory_sphenic_number(n) is False, (
            f"{n} has a repeated prime factor and should not be sphenic"
        )


def test_primes_are_not_sphenic():
    """A single prime is not a product of three primes."""
    primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47)
    for p in primes:
        assert number_theory_sphenic_number(p) is False, (
            f"{p} is a prime and should not be sphenic"
        )


def test_known_sphenic_sequence():
    """The first few sphenic numbers should be recognised in order."""
    expected = [30, 42, 66, 70, 78, 102, 105, 110, 114, 130]
    for n in expected:
        assert number_theory_sphenic_number(n) is True