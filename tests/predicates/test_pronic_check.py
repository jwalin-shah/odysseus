"""Tests for :func:`predicates.pronic_check.pronic_check`."""
import os
import sys

# Make the repository root importable so that ``predicates`` resolves as a
# top-level package regardless of how pytest is invoked.
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")),
)

import pytest

from predicates.pronic_check import pronic_check


# k * (k + 1) for k = 0..10 -- the canonical small pronic numbers.
PRONIC_NUMBERS = [0, 2, 6, 12, 20, 30, 42, 56, 72, 90, 110]


class TestKnownPronicNumbers:
    """Every well-known small pronic number must be accepted."""

    @pytest.mark.parametrize("n", PRONIC_NUMBERS)
    def test_small_pronic_numbers(self, n):
        assert pronic_check(n) is True

    def test_explicit_zero(self):
        # 0 = 0 * 1, so zero is a pronic number by convention.
        assert pronic_check(0) is True

    def test_explicit_two(self):
        # 2 = 1 * 2.
        assert pronic_check(2) is True

    def test_explicit_twelve(self):
        # 12 = 3 * 4.
        assert pronic_check(12) is True


class TestKnownNonPronicNumbers:
    """Small integers that are *not* pronic must be rejected."""

    @pytest.mark.parametrize("n", [1, 3, 4, 5, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17])
    def test_small_non_pronic_numbers(self, n):
        assert pronic_check(n) is False

    def test_one_is_not_pronic(self):
        assert pronic_check(1) is False

    def test_seven_is_not_pronic(self):
        assert pronic_check(7) is False

    def test_eight_is_not_pronic(self):
        assert pronic_check(8) is False


class TestNegativeAndZero:
    def test_negative_numbers_are_not_pronic(self):
        # Even though negative k can also produce positive products, the
        # standard definition restricts k to be non-negative.
        for n in [-1, -2, -6, -12, -100, -1_000_000]:
            assert pronic_check(n) is False


class TestNonIntegerInputs:
    def test_float_with_integer_value_is_rejected(self):
        assert pronic_check(2.0) is False

    def test_non_integer_float_is_rejected(self):
        assert pronic_check(2.5) is False
        assert pronic_check(0.0) is False

    def test_string_is_rejected(self):
        assert pronic_check("6") is False
        assert pronic_check("0") is False

    def test_none_is_rejected(self):
        assert pronic_check(None) is False

    def test_containers_are_rejected(self):
        assert pronic_check([2, 3]) is False
        assert pronic_check((1, 2)) is False
        assert pronic_check({6}) is False
        assert pronic_check({"value": 6}) is False


class TestBooleanInputs:
    def test_true_is_not_pronic(self):
        # ``bool`` is a subclass of ``int`` in Python, but True/False are
        # not considered pronic by this predicate.
        assert pronic_check(True) is False

    def test_false_is_not_pronic(self):
        assert pronic_check(False) is False


class TestLargeInputs:
    def test_one_thousand_pronic(self):
        # 1000 * 1001 = 1_001_000
        assert pronic_check(1_001_000) is True

    def test_one_million_pronic(self):
        # 1_000_000 * 1_000_001 = 1_000_001_000_000
        n = 1_000_000
        assert pronic_check(n * (n + 1)) is True

    def test_large_non_pronic(self):
        # 1_000_001 sits between 1000*1001 and 1001*1002, so it is not pronic.
        assert pronic_check(1_000_001) is False

    def test_very_large_pronic(self):
        # 10**9 * (10**9 + 1) is comfortably beyond the 32-bit range.
        k = 10**9
        assert pronic_check(k * (k + 1)) is True


class TestReturnType:
    def test_returns_boolean_true(self):
        assert pronic_check(2) is True
        assert pronic_check(2) == True  # noqa: E712 -- explicit bool compare

    def test_returns_boolean_false(self):
        assert pronic_check(3) is False
        assert pronic_check(3) == False  # noqa: E712 -- explicit bool compare