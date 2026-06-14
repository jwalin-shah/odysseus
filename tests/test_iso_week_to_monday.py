import os
import sys
from datetime import date

import pytest

# Make the implementation module importable when pytest is invoked from the
# repository root without installing the package.
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from iso_week_to_monday import iso_week_to_monday  # noqa: E402


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------

def test_basic_case_2021_w01():
    """2021-01-04 is the Monday of ISO week 1 of 2021."""
    result = iso_week_to_monday(2021, 1)
    assert result == date(2021, 1, 4)
    assert result.weekday() == 0  # Monday


def test_week_53_of_2020():
    """2020 is a 53-week ISO year; W53 begins on 2020-12-28."""
    result = iso_week_to_monday(2020, 53)
    assert result == date(2020, 12, 28)
    assert result.weekday() == 0


def test_week_53_of_2015():
    """2015 is a 53-week ISO year; W53 begins on 2015-12-28."""
    result = iso_week_to_monday(2015, 53)
    assert result == date(2015, 12, 28)
    assert result.weekday() == 0


def test_week_01_of_2024():
    """2024-01-01 is itself a Monday and the first day of ISO W1 2024."""
    result = iso_week_to_monday(2024, 1)
    assert result == date(2024, 1, 1)
    assert result.weekday() == 0


def test_week_01_starts_in_previous_gregorian_year():
    """2009 W1 begins on 2008-12-29 (the year boundary is not the week boundary)."""
    result = iso_week_to_monday(2009, 1)
    assert result == date(2008, 12, 29)
    assert result.weekday() == 0


def test_week_52_of_2021():
    """2021 W52 begins on 2021-12-27."""
    result = iso_week_to_monday(2021, 52)
    assert result == date(2021, 12, 27)
    assert result.weekday() == 0


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "year, week",
    [
        (2020, 1), (2020, 26), (2020, 52), (2020, 53),
        (2021, 1), (2021, 52),
        (2024, 1),
        (2015, 53),
        (2009, 1),
        (2008, 1),
    ],
)
def test_returned_date_is_always_monday(year, week):
    """The function must always return a Monday."""
    result = iso_week_to_monday(year, week)
    assert isinstance(result, date)
    assert result.weekday() == 0, (
        "Result for ISO year={} week={} is {} (weekday {}), expected Monday"
        .format(year, week, result, result.weekday())
    )


@pytest.mark.parametrize(
    "d",
    [
        date(2021, 1, 4),
        date(2020, 12, 31),
        date(2015, 12, 31),
        date(2008, 12, 29),
        date(2023, 6, 15),
        date(2024, 1, 1),
        date(2022, 1, 1),  # Saturday - belongs to W52 of 2021
    ],
)
def test_roundtrip_with_date_isocalendar(d):
    """Converting via isocalendar() and back must agree on the Monday."""
    iso_year, iso_week, iso_day = d.isocalendar()
    monday = iso_week_to_monday(iso_year, iso_week)
    assert monday.weekday() == 0
    # The original date is ``iso_day - 1`` days after the Monday.
    assert (d - monday).days == iso_day - 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_invalid_week_zero_raises_value_error():
    with pytest.raises(ValueError):
        iso_week_to_monday(2021, 0)


def test_invalid_week_54_raises_value_error():
    with pytest.raises(ValueError):
        iso_week_to_monday(2021, 54)


def test_week_53_in_52_week_year_raises_value_error():
    """2021 has only 52 ISO weeks, so W53 must be rejected."""
    with pytest.raises(ValueError):
        iso_week_to_monday(2021, 53)


def test_negative_week_raises_value_error():
    with pytest.raises(ValueError):
        iso_week_to_monday(2021, -1)


def test_string_year_raises_type_error():
    with pytest.raises(TypeError):
        iso_week_to_monday("2021", 1)


def test_string_week_raises_type_error():
    with pytest.raises(TypeError):
        iso_week_to_monday(2021, "1")


def test_float_year_raises_type_error():
    with pytest.raises(TypeError):
        iso_week_to_monday(2021.0, 1)


def test_none_year_raises_type_error():
    with pytest.raises(TypeError):
        iso_week_to_monday(None, 1)


def test_bool_year_raises_type_error():
    with pytest.raises(TypeError):
        iso_week_to_monday(True, 1)


def test_bool_week_raises_type_error():
    with pytest.raises(TypeError):
        iso_week_to_monday(2021, True)