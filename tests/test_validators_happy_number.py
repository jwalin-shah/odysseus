import pytest

from src.validators_happy_number import validators_happy_number


def test_known_happy_19():
    """19 is the classic textbook example of a happy number."""
    assert validators_happy_number(19) is True


def test_trivially_happy_1():
    """1 is happy because it is already equal to 1."""
    assert validators_happy_number(1) is True


def test_known_happy_7():
    """7 is a well-known happy number."""
    assert validators_happy_number(7) is True


def test_known_happy_10():
    """10 is a happy number (1 + 0 = 1)."""
    assert validators_happy_number(10) is True


def test_known_happy_100():
    """100 is a happy number (1 + 0 + 0 = 1)."""
    assert validators_happy_number(100) is True


def test_known_unhappy_2():
    """2 enters the unhappy cycle {2, 4, 16, 37, 58, 89, 145, ...}."""
    assert validators_happy_number(2) is False


def test_known_unhappy_3():
    """3 is not a happy number."""
    assert validators_happy_number(3) is False


def test_known_unhappy_4():
    """4 is not a happy number and is part of the unhappy cycle."""
    assert validators_happy_number(4) is False


def test_zero_is_unhappy():
    """0 loops forever at 0 and is therefore unhappy."""
    assert validators_happy_number(0) is False


def test_negative_is_unhappy():
    """Negative inputs are not happy numbers."""
    assert validators_happy_number(-19) is False


def test_non_integer_string_is_unhappy():
    """String input is not a valid integer and is not happy."""
    assert validators_happy_number("19") is False


def test_non_integer_float_is_unhappy():
    """Float input is not a valid integer and is not happy."""
    assert validators_happy_number(1.5) is False


def test_boolean_is_unhappy():
    """Booleans are not treated as integers by the validator."""
    assert validators_happy_number(True) is False
    assert validators_happy_number(False) is False


def test_none_is_unhappy():
    """``None`` is not a valid integer and is not happy."""
    assert validators_happy_number(None) is False


def test_terminates_on_large_unhappy_number():
    """A large unhappy number should still resolve quickly via cycle detection."""
    assert validators_happy_number(2 ** 31) is False


def test_happy_number_batch():
    """A batch of known happy numbers should all return ``True``."""
    for n in (1, 7, 10, 13, 19, 23, 28, 31, 32, 44, 49, 68, 70, 79, 82, 86, 91, 94, 97, 100):
        assert validators_happy_number(n) is True, f"{n} should be happy"


def test_unhappy_number_batch():
    """A batch of known unhappy numbers should all return ``False``."""
    for n in (2, 3, 4, 5, 6, 8, 9, 11, 12, 14, 15, 16, 17, 18, 20):
        assert validators_happy_number(n) is False, f"{n} should be unhappy"