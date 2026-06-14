"""Tests for ``missions.iso_week_monday_date_locator.iso_week_monday_date_locator``."""
import sys
from datetime import date
from pathlib import Path

import pytest

# Make the project root importable when pytest is invoked from anywhere.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from missions.iso_week_monday_date_locator import (  # noqa: E402  (sys.path tweak above)
    iso_week_monday_date_locator,
)


# ---------------------------------------------------------------------------
# Happy-path / known reference dates
# ---------------------------------------------------------------------------
class TestKnownIsoWeeks:
    """A handful of well-known ISO week -> Monday mappings."""

    def test_2020_week_1(self):
        # 2020-01-01 is a Wednesday; ISO week 1 of 2020 actually starts on
        # Monday 2019-12-30 and runs through Sunday 2020-01-05.
        assert iso_week_monday_date_locator(2020, 1) == date(2019, 12, 30)

    def test_2021_week_1(self):
        # 2021-01-01 is a Friday (in ISO week 53 of 2020).  ISO week 1 of
        # 2021 therefore starts on Monday 2021-01-04.
        assert iso_week_monday_date_locator(2021, 1) == date(2021, 1, 4)

    def test_2022_week_1(self):
        # 2022-01-01 is a Saturday (in ISO week 52 of 2021).  ISO week 1
        # of 2022 starts on Monday 2022-01-03.
        assert iso_week_monday_date_locator(2022, 1) == date(2022, 1, 3)

    def test_2018_week_1(self):
        # 2018-01-01 is a Monday, so week 1 of 2018 starts on that very day.
        assert iso_week_monday_date_locator(2018, 1) == date(2018, 1, 1)

    def test_2024_week_1(self):
        # 2024-01-01 is a Monday, so week 1 of 2024 starts on that day.
        assert iso_week_monday_date_locator(2024, 1) == date(2024, 1, 1)

    def test_2020_week_53(self):
        # 2020 is one of the years that has 53 ISO weeks.  The Monday of
        # week 53 is 2020-12-28.
        assert iso_week_monday_date_locator(2020, 53) == date(2020, 12, 28)

    def test_2015_week_53(self):
        # 2015 also has 53 ISO weeks; week 53 starts on Monday 2015-12-28.
        assert iso_week_monday_date_locator(2015, 53) == date(2015, 12, 28)


# ---------------------------------------------------------------------------
# Return-type / structural guarantees
# ---------------------------------------------------------------------------
class TestReturnType:
    def test_returns_date_instance(self):
        result = iso_week_monday_date_locator(2024, 1)
        assert isinstance(result, date)

    def test_returned_date_is_always_monday(self):
        """Every successful call must return a Monday (weekday() == 0)."""
        for year in range(2015, 2031):
            for week in (1, 13, 26, 39, 52):
                result = iso_week_monday_date_locator(year, week)
                assert result.weekday() == 0, (
                    f"iso_week_monday_date_locator({year}, {week}) returned "
                    f"{result} (weekday={result.weekday()}), expected Monday"
                )

    def test_result_round_trips_through_isocalendar(self):
        """The result's ISO (year, week) must match what was requested."""
        for year in range(2015, 2031):
            for week in (1, 26, 52):
                result = iso_week_monday_date_locator(year, week)
                iso_year, iso_week, iso_day = result.isocalendar()
                assert iso_year == year
                assert iso_week == week
                assert iso_day == 1  # Monday


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
class TestInvalidInput:
    def test_week_zero_raises_value_error(self):
        with pytest.raises(ValueError):
            iso_week_monday_date_locator(2020, 0)

    def test_negative_week_raises_value_error(self):
        with pytest.raises(ValueError):
            iso_week_monday_date_locator(2020, -1)

    def test_week_54_raises_value_error(self):
        with pytest.raises(ValueError):
            iso_week_monday_date_locator(2020, 54)

    def test_week_53_in_52_week_year_raises_value_error(self):
        # 2021 has only 52 ISO weeks.
        with pytest.raises(ValueError):
            iso_week_monday_date_locator(2021, 53)

    def test_week_53_in_2022_raises_value_error(self):
        # 2022 has only 52 ISO weeks.
        with pytest.raises(ValueError):
            iso_week_monday_date_locator(2022, 53)

    @pytest.mark.parametrize("bad", [1.0, "1", None, True, False])
    def test_non_integer_week_raises_type_error(self, bad):
        with pytest.raises(TypeError):
            iso_week_monday_date_locator(2020, bad)

    @pytest.mark.parametrize("bad", [2020.0, "2020", None, True, False])
    def test_non_integer_year_raises_type_error(self, bad):
        with pytest.raises(TypeError):
            iso_week_monday_date_locator(bad, 1)


# ---------------------------------------------------------------------------
# Round-trip property test
# ---------------------------------------------------------------------------
class TestRoundTrip:
    @pytest.mark.parametrize(
        "year, week",
        [
            (2015, 1), (2015, 53),
            (2016, 1), (2016, 52),
            (2020, 1), (2020, 27), (2020, 53),
            (2021, 1), (2021, 52),
            (2022, 1), (2022, 30), (2022, 52),
            (2023, 1), (2023, 52),
            (2024, 1), (2024, 52),
        ],
    )
    def test_locator_then_isocalendar(self, year, week):
        """For any valid (year, week) the locator returns a date whose
        ``isocalendar()`` agrees with the input on the (year, week) pair
        and whose weekday is Monday (== 1 in ISO terms)."""
        result = iso_week_monday_date_locator(year, week)
        iso_year, iso_week, iso_day = result.isocalendar()
        assert (iso_year, iso_week) == (year, week)
        assert iso_day == 1
        assert result.weekday() == 0  # Monday in Python's convention too.