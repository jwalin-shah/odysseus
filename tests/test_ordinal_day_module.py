"""Tests for ``ordinal_day_module``."""

import pytest
from datetime import date, datetime

from ordinal_day_module import is_leap_year, ordinal_day, from_ordinal_day


# --------------------------------------------------------------------------- #
# is_leap_year                                                                #
# --------------------------------------------------------------------------- #

class TestIsLeapYear:
    @pytest.mark.parametrize("year", [1992, 1996, 2004, 2020, 2024, 2028])
    def test_divisible_by_4_is_leap(self, year):
        assert is_leap_year(year) is True

    @pytest.mark.parametrize("year", [1700, 1800, 1900, 2100, 2200, 2300])
    def test_divisible_by_100_not_400_is_common(self, year):
        assert is_leap_year(year) is False

    @pytest.mark.parametrize("year", [1600, 2000, 2400, 2800])
    def test_divisible_by_400_is_leap(self, year):
        assert is_leap_year(year) is True

    @pytest.mark.parametrize("year", [1999, 2001, 2023, 2025, 2099])
    def test_typical_common_years(self, year):
        assert is_leap_year(year) is False

    def test_zero_year_is_leap(self):
        # Year 0 is divisible by 400 (0 % 400 == 0) so the rule says leap.
        assert is_leap_year(0) is True

    def test_negative_year(self):
        # -4 is divisible by 4, not by 100, so leap.
        assert is_leap_year(-4) is True
        assert is_leap_year(-1) is False

    @pytest.mark.parametrize("bad", [1.0, "2024", None, True, False, [2024]])
    def test_non_integer_raises_type_error(self, bad):
        with pytest.raises(TypeError):
            is_leap_year(bad)


# --------------------------------------------------------------------------- #
# ordinal_day                                                                 #
# --------------------------------------------------------------------------- #

class TestOrdinalDay:
    def test_january_first_is_one(self):
        assert ordinal_day(date(2023, 1, 1)) == 1
        assert ordinal_day(date(1999, 1, 1)) == 1
        assert ordinal_day(date(2000, 1, 1)) == 1

    def test_january_31_is_31(self):
        assert ordinal_day(date(2023, 1, 31)) == 31

    def test_february_first_non_leap(self):
        # 31 (Jan) + 1 = 32
        assert ordinal_day(date(2023, 2, 1)) == 32

    def test_february_first_leap(self):
        # 31 (Jan) + 1 = 32 (leap year only changes Feb 29)
        assert ordinal_day(date(2024, 2, 1)) == 32

    def test_march_first_non_leap(self):
        # 31 + 28 + 1 = 60
        assert ordinal_day(date(2023, 3, 1)) == 60

    def test_march_first_leap(self):
        # 31 + 29 + 1 = 61
        assert ordinal_day(date(2024, 3, 1)) == 61

    def test_february_28_leap(self):
        # 31 + 28 = 59
        assert ordinal_day(date(2024, 2, 28)) == 59

    def test_february_29_leap(self):
        # 31 + 29 = 60
        assert ordinal_day(date(2024, 2, 29)) == 60

    def test_july_4_non_leap(self):
        # 31 + 28 + 31 + 30 + 31 + 30 + 4 = 185
        assert ordinal_day(date(2023, 7, 4)) == 185

    def test_december_30_non_leap(self):
        assert ordinal_day(date(2023, 12, 30)) == 364

    def test_december_31_non_leap_is_365(self):
        assert ordinal_day(date(2023, 12, 31)) == 365

    def test_december_31_leap_is_366(self):
        assert ordinal_day(date(2024, 12, 31)) == 366

    def test_accepts_datetime(self):
        # Time component must be ignored.
        assert ordinal_day(datetime(2023, 7, 4, 0, 0, 0)) == 185
        assert ordinal_day(datetime(2023, 7, 4, 23, 59, 59)) == 185
        assert ordinal_day(datetime(2024, 12, 31, 12, 0, 0)) == 366

    def test_accepts_datetime_with_microseconds(self):
        assert ordinal_day(datetime(2024, 1, 1, 0, 0, 0, 1)) == 1

    @pytest.mark.parametrize("bad", [
        "2023-01-01", 20230101, 1.5, None, [], {}, object(),
    ])
    def test_invalid_type_raises_type_error(self, bad):
        with pytest.raises(TypeError):
            ordinal_day(bad)

    def test_result_is_int(self):
        result = ordinal_day(date(2023, 5, 5))
        assert isinstance(result, int)

    @pytest.mark.parametrize("d,expected", [
        (date(2023, 1, 1), 1),
        (date(2023, 1, 31), 31),
        (date(2023, 2, 28), 59),
        (date(2023, 3, 1), 60),
        (date(2023, 6, 15), 166),
        (date(2023, 12, 31), 365),
        (date(2024, 1, 1), 1),
        (date(2024, 2, 29), 60),
        (date(2024, 3, 1), 61),
        (date(2024, 12, 31), 366),
        (date(2000, 12, 31), 366),
        (date(1900, 12, 31), 365),
    ])
    def test_parametrized_dates(self, d, expected):
        assert ordinal_day(d) == expected


# --------------------------------------------------------------------------- #
# from_ordinal_day                                                            #
# --------------------------------------------------------------------------- #

class TestFromOrdinalDay:
    @pytest.mark.parametrize("d", [
        date(2023, 1, 1),
        date(2023, 1, 31),
        date(2023, 2, 28),
        date(2023, 3, 1),
        date(2023, 6, 15),
        date(2023, 12, 31),
        date(2024, 2, 29),
        date(2024, 12, 31),
        date(2000, 12, 31),
        date(1900, 12, 31),
    ])
    def test_round_trip(self, d):
        assert from_ordinal_day(d.year, ordinal_day(d)) == d

    def test_first_day_of_year(self):
        assert from_ordinal_day(2023, 1) == date(2023, 1, 1)
        assert from_ordinal_day(2024, 1) == date(2024, 1, 1)

    def test_last_day_common_year(self):
        assert from_ordinal_day(2023, 365) == date(2023, 12, 31)

    def test_last_day_leap_year(self):
        assert from_ordinal_day(2024, 366) == date(2024, 12, 31)

    def test_february_29_in_leap_year(self):
        assert from_ordinal_day(2024, 60) == date(2024, 2, 29)

    def test_february_28_in_leap_year(self):
        assert from_ordinal_day(2024, 59) == date(2024, 2, 28)

    def test_march_first_in_leap_year(self):
        assert from_ordinal_day(2024, 61) == date(2024, 3, 1)

    @pytest.mark.parametrize("ordinal", [0, -1, -100])
    def test_ordinal_too_low_raises(self, ordinal):
        with pytest.raises(ValueError):
            from_ordinal_day(2023, ordinal)

    def test_ordinal_too_high_common_year_raises(self):
        with pytest.raises(ValueError):
            from_ordinal_day(2023, 366)

    def test_ordinal_too_high_leap_year_raises(self):
        with pytest.raises(ValueError):
            from_ordinal_day(2024, 367)

    def test_ordinal_at_leap_year_max_is_ok(self):
        # 366 is valid in a leap year.
        assert from_ordinal_day(2024, 366) == date(2024, 12, 31)

    def test_ordinal_at_common_year_max_is_ok(self):
        # 365 is the last valid day in a common year.
        assert from_ordinal_day(2023, 365) == date(2023, 12, 31)

    @pytest.mark.parametrize("bad_year", [2024.0, "2024", None, True, [2024]])
    def test_non_int_year_raises(self, bad_year):
        with pytest.raises(TypeError):
            from_ordinal_day(bad_year, 1)

    @pytest.mark.parametrize("bad_ord", [1.0, "1", None, True, [1]])
    def test_non_int_ordinal_raises(self, bad_ord):
        with pytest.raises(TypeError):
            from_ordinal_day(2023, bad_ord)