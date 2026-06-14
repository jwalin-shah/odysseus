"""Tests for ``niven_predicate``."""

import pytest

from niven_predicate import niven_predicate


class TestNivenPredicate:
    """Direct unit tests for the ``niven_predicate`` function."""

    def test_single_digit_numbers_are_all_niven(self):
        # Every single-digit number n has digit sum n, and n % n == 0.
        for number in range(1, 10):
            assert niven_predicate(number) is True, (
                f"Expected {number} to be a Niven number"
            )

    def test_known_niven_numbers(self):
        niven_numbers = [
            1, 2, 3, 4, 5, 6, 7, 8, 9,  # single digits
            10,                           # 1 + 0 = 1, 10 % 1 == 0
            12,                           # 1 + 2 = 3, 12 % 3 == 0
            18,                           # 1 + 8 = 9, 18 % 9 == 0
            20,                           # 2 + 0 = 2, 20 % 2 == 0
            21,                           # 2 + 1 = 3, 21 % 3 == 0
            24,                           # 2 + 4 = 6, 24 % 6 == 0
            27,                           # 2 + 7 = 9, 27 % 9 == 0
            100,                          # 1 + 0 + 0 = 1, 100 % 1 == 0
            111,                          # 1 + 1 + 1 = 3, 111 % 3 == 0
            999,                          # 9 + 9 + 9 = 27, 999 % 27 == 0
        ]
        for number in niven_numbers:
            assert niven_predicate(number) is True, (
                f"Expected {number} to be a Niven number"
            )

    def test_known_non_niven_numbers(self):
        non_niven_numbers = [
            11,    # 1 + 1 = 2, 11 % 2 == 1
            13,    # 1 + 3 = 4, 13 % 4 == 1
            14,    # 1 + 4 = 5, 14 % 5 == 4
            15,    # 1 + 5 = 6, 15 % 6 == 3
            16,    # 1 + 6 = 7, 16 % 7 == 2
            17,    # 1 + 7 = 8, 17 % 8 == 1
            19,    # 1 + 9 = 10, 19 % 10 == 9
            22,    # 2 + 2 = 4, 22 % 4 == 2
            23,    # 2 + 3 = 5, 23 % 5 == 3
            25,    # 2 + 5 = 7, 25 % 7 == 4
            101,   # 1 + 0 + 1 = 2, 101 % 2 == 1
        ]
        for number in non_niven_numbers:
            assert niven_predicate(number) is False, (
                f"Expected {number} NOT to be a Niven number"
            )

    def test_zero_is_not_niven(self):
        # 0 is not a positive integer and would cause division by zero
        # when computing the digit sum.
        assert niven_predicate(0) is False

    def test_negative_numbers_are_not_niven(self):
        # The standard definition requires positive integers.
        assert niven_predicate(-1) is False
        assert niven_predicate(-10) is False
        assert niven_predicate(-12) is False
        assert niven_predicate(-100) is False
        assert niven_predicate(-18) is False

    def test_non_integer_inputs_return_false(self):
        # Floats, strings, None, lists, etc. should all return False
        # rather than raising an exception.
        invalid_inputs = [
            1.0,
            1.5,
            "12",
            "18",
            None,
            [12],
            (12,),
            {12},
            {"n": 12},
            complex(12, 0),
        ]
        for value in invalid_inputs:
            assert niven_predicate(value) is False, (
                f"Expected niven_predicate({value!r}) to be False"
            )

    def test_boolean_inputs_return_false(self):
        # Booleans are technically ints in Python, but should not be
        # accepted as valid inputs to a number-property predicate.
        assert niven_predicate(True) is False
        assert niven_predicate(False) is False

    def test_returns_boolean_type(self):
        # The function should always return a real ``bool``, not just a
        # truthy/falsy value.
        assert isinstance(niven_predicate(18), bool)
        assert isinstance(niven_predicate(19), bool)
        assert isinstance(niven_predicate(0), bool)
        assert isinstance(niven_predicate(-1), bool)

    def test_large_niven_number(self):
        # 1008: 1 + 0 + 0 + 8 = 9, 1008 % 9 == 0  (1008 / 9 == 112)
        assert niven_predicate(1008) is True
        # 1009: 1 + 0 + 0 + 9 = 10, 1009 % 10 == 9
        assert niven_predicate(1009) is False


@pytest.mark.parametrize(
    "number,expected",
    [
        (1, True),
        (2, True),
        (9, True),
        (10, True),
        (11, False),
        (12, True),
        (18, True),
        (19, False),
        (20, True),
        (21, True),
        (22, False),
        (100, True),
        (101, False),
        (108, True),
        (120, True),
    ],
)
def test_niven_predicate_parametrized(number, expected):
    """Parametrized sanity-check covering a spread of small numbers."""
    assert niven_predicate(number) is expected