import os
import sys

# Make the project root importable so `from date_math...` resolves
# regardless of where pytest is invoked from.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pytest
from datetime import date

from date_math.nth_weekday import nth_weekday


# ---- positive n: count from the start of the month -----------------------

def test_first_monday_jan_2024():
    # Jan 1, 2024 is itself a Monday.
    assert nth_weekday(2024, 1, 0, 1) == date(2024, 1, 1)


def test_second_monday_jan_2024():
    assert nth_weekday(2024, 1, 0, 2) == date(2024, 1, 8)


def test_fifth_monday_jan_2024():
    # Jan 2024 has five Mondays: 1, 8, 15, 22, 29.
    assert nth_weekday(2024, 1, 0, 5) == date(2024, 1, 29)


def test_third_friday_feb_2024():
    # Feb 2, 2024 is a Friday; 3rd Friday is Feb 16.
    assert nth_weekday(2024, 2, 4, 3) == date(2024, 2, 16)


def test_second_thursday_feb_2024():
    # Feb 1, 2024 is a Thursday; 2nd Thursday is Feb 8.
    assert nth_weekday(2024, 2, 3, 2) == date(2024, 2, 8)


def test_first_sunday_mar_2024():
    # March 3, 2024 is the first Sunday of March 2024.
    assert nth_weekday(2024, 3, 6, 1) == date(2024, 3, 3)


def test_fourth_saturday_feb_2024():
    # Feb 3, 2024 is the first Saturday; 4th Saturday is Feb 24.
    assert nth_weekday(2024, 2, 5, 4) == date(2024, 2, 24)


# ---- edge cases ---------------------------------------------------------

def test_returns_date_subclass():
    result = nth_weekday(2024, 1, 0, 1)
    assert isinstance(result, date)


def test_fifth_monday_does_not_exist_in_feb_2024():
    # Feb 2024 has only 29 days; there cannot be a 5th Monday.
    with pytest.raises(ValueError):
        nth_weekday(2024, 2, 0, 5)


def test_invalid_weekday_raises():
    with pytest.raises(ValueError):
        nth_weekday(2024, 1, 7, 1)


def test_invalid_month_raises():
    with pytest.raises(ValueError):
        nth_weekday(2024, 13, 0, 1)


def test_invalid_n_raises():
    with pytest.raises(ValueError):
        nth_weekday(2024, 1, 0, 0)
    with pytest.raises(ValueError):
        nth_weekday(2024, 1, 0, -1)


def test_leap_year_handling():
    # Feb 29 only exists in a leap year; 2024 is a leap year.
    assert nth_weekday(2020, 2, 5, 4) == date(2020, 2, 22)