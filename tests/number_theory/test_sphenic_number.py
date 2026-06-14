"""Tests for :mod:`number_theory.sphenic_number`."""
import os
import sys

import pytest

# Make the project root importable so ``from number_theory import ...`` works
# regardless of where pytest is invoked from.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from number_theory.sphenic_number import sphenic_number  # noqa: E402


# ---------------------------------------------------------------------------
# Positive cases - well known sphenic numbers (product of three distinct primes)
# ---------------------------------------------------------------------------
class TestSphenicNumberTrue:
    def test_smallest_sphenic_number(self):
        # 30 = 2 * 3 * 5
        assert sphenic_number(30) is True

    def test_42(self):
        # 42 = 2 * 3 * 7
        assert sphenic_number(42) is True

    def test_66(self):
        # 66 = 2 * 3 * 11
        assert sphenic_number(66) is True

    def test_70(self):
        # 70 = 2 * 5 * 7
        assert sphenic_number(70) is True

    def test_78(self):
        # 78 = 2 * 3 * 13
        assert sphenic_number(78) is True

    def test_102(self):
        # 102 = 2 * 3 * 17
        assert sphenic_number(102) is True

    def test_105(self):
        # 105 = 3 * 5 * 7
        assert sphenic_number(105) is True

    def test_110(self):
        # 110 = 2 * 5 * 11
        assert sphenic_number(110) is True

    def test_large_sphenic(self):
        # 2 * 3 * 1009 = 6054
        assert sphenic_number(6054) is True


# ---------------------------------------------------------------------------
# Negative cases
# ---------------------------------------------------------------------------
class TestSphenicNumberFalse:
    def test_zero_is_not_sphenic(self):
        assert sphenic_number(0) is False

    def test_one_is_not_sphenic(self):
        assert sphenic_number(1) is False

    def test_prime_is_not_sphenic(self):
        # A single prime has only one prime factor.
        assert sphenic_number(2) is False
        assert sphenic_number(3) is False
        assert sphenic_number(7) is False
        assert sphenic_number(101) is False

    def test_product_of_two_primes_is_not_sphenic(self):
        # 6 = 2 * 3
        assert sphenic_number(6) is False
        # 15 = 3 * 5
        assert sphenic_number(15) is False
        # 35 = 5 * 7
        assert sphenic_number(35) is False

    def test_squared_prime_factor_is_not_sphenic(self):
        # 60 = 2**2 * 3 * 5 - one prime factor appears twice
        assert sphenic_number(60) is False
        # 12 = 2**2 * 3
        assert sphenic_number(12) is False
        # 100 = 2**2 * 5**2
        assert sphenic_number(100) is False

    def test_perfect_square_is_not_sphenic(self):
        # 36 = 2**2 * 3**2 - every prime factor appears twice
        assert sphenic_number(36) is False

    def test_four_distinct_primes_is_not_sphenic(self):
        # 210 = 2 * 3 * 5 * 7
        assert sphenic_number(210) is False
        # 2310 = 2 * 3 * 5 * 7 * 11
        assert sphenic_number(2310) is False

    def test_negative_is_not_sphenic(self):
        assert sphenic_number(-30) is False
        assert sphenic_number(-1) is False

    def test_non_integer_inputs_are_not_sphenic(self):
        assert sphenic_number(30.0) is False
        assert sphenic_number("30") is False
        assert sphenic_number(None) is False
        assert sphenic_number([30]) is False

    def test_boolean_inputs_are_not_sphenic(self):
        # bool is a subclass of int but should not be treated as a number.
        assert sphenic_number(True) is False
        assert sphenic_number(False) is False

    def test_all_numbers_below_30_are_not_sphenic(self):
        # 30 is the smallest sphenic number, so everything below must fail.
        for value in range(1, 30):
            assert sphenic_number(value) is False, (
                f"{value} was incorrectly reported as sphenic"
            )


# ---------------------------------------------------------------------------
# Parametrised sanity checks
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value",
    [30, 42, 66, 70, 78, 102, 105, 110, 114, 130, 138, 154, 165, 170, 182, 190, 195],
)
def test_parametrised_sphenic_true(value):
    """Each of these integers is the product of exactly three distinct primes."""
    assert sphenic_number(value) is True


@pytest.mark.parametrize(
    "value",
    [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 16, 24, 36, 48, 60, 120, 210, 2310, 1000],
)
def test_parametrised_sphenic_false(value):
    """None of these integers satisfy the definition of a sphenic number."""
    assert sphenic_number(value) is False