"""Tests for the isbn_validator module."""
import pytest
from isbn_validator import is_valid_isbn


# ----- Valid ISBN-10s -----
VALID_ISBN10 = [
    '0306406152',       # classic valid example
    '123456789X',       # 123456789X -> sum 220, divisible by 11
    '0471958697',       # known valid
    '043942089X',       # valid with X check digit
    '020161622X',       # valid with X check digit
]

# ----- Valid ISBN-13s -----
VALID_ISBN13 = [
    '9780306406157',    # classic valid example
    '9783161484100',    # valid
    '9781861972712',    # valid
    '978-0-306-40615-7',  # with hyphens
]

# ----- Invalid ISBN-10s (wrong checksum or bad characters) -----
INVALID_ISBN10 = [
    '1234567890',       # wrong check digit (210 % 11 != 0)
    '123456789Y',       # Y is not a valid check digit
    '123456789x1',      # too long
    '12345678',         # too short
    'abcdefghij',       # all letters
    '0306406153',       # off-by-one check digit
]

# ----- Invalid ISBN-13s -----
INVALID_ISBN13 = [
    '9780306406158',    # wrong check digit
    '978030640615',     # too short
    '97803064061570',   # too long
    '978030640615X',    # contains letter
]


class TestValidISBN10:
    @pytest.mark.parametrize("value", VALID_ISBN10)
    def test_isbn10_valid(self, value):
        assert is_valid_isbn(value) is True

    def test_isbn10_lowercase_x(self):
        # '123456789x' (lowercase) should also be valid
        assert is_valid_isbn('123456789x') is True

    def test_isbn10_with_hyphens(self):
        assert is_valid_isbn('0-306-40615-2') is True

    def test_isbn10_with_spaces(self):
        assert is_valid_isbn('0 306 40615 2') is True


class TestValidISBN13:
    @pytest.mark.parametrize("value", VALID_ISBN13)
    def test_isbn13_valid(self, value):
        assert is_valid_isbn(value) is True

    def test_isbn13_with_spaces(self):
        assert is_valid_isbn('978 0 306 40615 7') is True


class TestInvalidInput:
    @pytest.mark.parametrize("value", INVALID_ISBN10)
    def test_isbn10_invalid(self, value):
        assert is_valid_isbn(value) is False

    @pytest.mark.parametrize("value", INVALID_ISBN13)
    def test_isbn13_invalid(self, value):
        assert is_valid_isbn(value) is False

    def test_empty_string(self):
        assert is_valid_isbn('') is False

    def test_none(self):
        assert is_valid_isbn(None) is False

    def test_non_string(self):
        assert is_valid_isbn(1234567890) is False
        assert is_valid_isbn(['0306406152']) is False
        assert is_valid_isbn(12.5) is False

    def test_wrong_length(self):
        assert is_valid_isbn('12345') is False
        assert is_valid_isbn('123456789012345') is False

    def test_pure_text(self):
        assert is_valid_isbn('not-an-isbn') is False


class TestReturnType:
    def test_returns_bool(self):
        result = is_valid_isbn('0306406152')
        assert isinstance(result, bool)
        assert result is True
        result2 = is_valid_isbn('1234567890')
        assert isinstance(result2, bool)
        assert result2 is False