"""
Tests for ``missions_iso_week_monday_date_locator``.

These tests exercise both calling conventions (date-in, and year+week-in)
and cover a handful of year/ISO-week boundary edge cases.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime

import pytest

# Make the ``src`` directory importable regardless of how pytest is invoked.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SRC_DIR = os.path.join(_REPO_ROOT, "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from missions_iso_week_monday_date_locator import (  # noqa: E402
    missions_iso_week_monday_date_locator,
)


# ---------------------------------------------------------------------------
# Convention A: pass a date, get the Monday of its ISO week.
# ---------------------------------------------------------------------------

class TestFromDate:
    def test_wednesday_returns_same_week_monday(self):
        # 2024-01-10 is a Wednesday; ISO 2024-W02; Monday is 2024-01-08.
        result = missions_iso_week_monday_date_locator(date(2024, 1, 10))
        assert result == date(2024, 1, 8)
        assert isinstance(result, date)

    def test_monday_returns_itself(self):
        # A Monday should be its own week's Monday.
        assert missions_iso_week_monday_date_locator(date(2024, 1, 8)) == date(2024, 1, 8)

    def test_sunday_returns_previous_monday(self):
        # 2024-01-14 is a Sunday; still ISO 2024-W02, Monday 2024-01-08.
        assert missions_iso_week_monday_date_locator(date(2024, 1, 14)) == date(2024, 1, 8)

    def test_jan_1_2023_belongs_to_previous_iso_year(self):
        # 2023-01-01 (Sunday) is in ISO 2022-W52, Monday 2022-12-26.
        result = missions_iso_week_monday_date_locator(date(2023, 1, 1))
        assert result == date(2022, 12, 26)
        assert result.isocalendar() == (2022, 52, 1)

    def test_dec_31_2024_belongs_to_next_iso_year(self):
        # 2024-12-31 (Tuesday) is in ISO 2025-W01, Monday 2024-12-30.
        result = missions_iso_week_monday_date_locator(date(2024, 12, 31))
        assert result == date(2024, 12, 30)
        assert result.isocalendar() == (2025, 1, 1)

    def test_datetime_input_is_accepted(self):
        # A datetime should be coerced to its date portion.
        dt = datetime(2024, 1, 10, 23, 59, 59)
        result = missions_iso_week_monday_date_locator(dt)
        assert result == date(2024, 1, 8)

    def test_string_input_is_rejected(self):
        with pytest.raises(TypeError):
            missions_iso_week_monday_date_locator("2024-01-10")  # type: ignore[arg-type]

    def test_none_input_is_rejected(self):
        with pytest.raises(TypeError):
            missions_iso_week_monday_date_locator(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Convention B: pass (iso_year, iso_week), get the Monday of that week.
# ---------------------------------------------------------------------------

class TestFromYearAndWeek:
    def test_week_1_of_2024_starts_on_jan_1(self):
        # 2024 starts on a Monday, so ISO 2024-W01 begins 2024-01-01.
        assert missions_iso_week_monday_date_locator(2024, 1) == date(2024, 1, 1)

    def test_week_2_of_2024_starts_on_jan_8(self):
        assert missions_iso_week_monday_date_locator(2024, 2) == date(2024, 1, 8)

    def test_week_52_of_2024_starts_on_dec_23(self):
        assert missions_iso_week_monday_date_locator(2024, 52) == date(2024, 12, 23)

    def test_week_53_of_2020_exists(self):
        # 2020 has 53 ISO weeks; week 53 starts on 2020-12-28.
        assert missions_iso_week_monday_date_locator(2020, 53) == date(2020, 12, 28)

    def test_week_53_of_2021_does_not_exist(self):
        # 2021 only has 52 ISO weeks.
        with pytest.raises(ValueError):
            missions_iso_week_monday_date_locator(2021, 53)

    def test_week_53_of_2015_exists(self):
        # 2015 has 53 ISO weeks; week 53 starts on 2015-12-28.
        assert missions_iso_week_monday_date_locator(2015, 53) == date(2015, 12, 28)

    def test_week_zero_is_rejected(self):
        with pytest.raises(ValueError):
            missions_iso_week_monday_date_locator(2024, 0)

    def test_week_54_is_rejected(self):
        with pytest.raises(ValueError):
            missions_iso_week_monday_date_locator(2024, 54)

    def test_negative_week_is_rejected(self):
        with pytest.raises(ValueError):
            missions_iso_week_monday_date_locator(2024, -1)

    def test_year_only_is_rejected(self):
        with pytest.raises(ValueError):
            missions_iso_week_monday_date_locator(2024)

    def test_week_must_be_int(self):
        with pytest.raises(TypeError):
            missions_iso_week_monday_date_locator(2024, "1")  # type: ignore[arg-type]

    def test_year_must_be_int(self):
        with pytest.raises(TypeError):
            missions_iso_week_monday_date_locator("2024", 1)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Cross-convention consistency: every date-in call must agree with the
# year+week-in call for the same ISO week.
# ---------------------------------------------------------------------------

class TestConsistencyBetweenConventions:
    @pytest.mark.parametrize(
        "iso_year, iso_week, expected_monday",
        [
            (2020, 1, date(2019, 12, 30)),   # 2020-W01 straddles into 2019
            (2020, 53, date(2020, 12, 28)),  # 2020 has 53 weeks
            (2023, 1, date(2023, 1, 2)),
            (2024, 1, date(2024, 1, 1)),
            (2024, 52, date(2024, 12, 23)),
            (2025, 1, date(2024, 12, 30)),   # 2025-W01 begins Dec 30 2024
            (2026, 1, date(2025, 12, 29)),   # 2026-W01 begins Dec 29 2025
        ],
    )
    def test_year_week_matches_isocalendar_for_monday(self, iso_year, iso_week, expected_monday):
        assert missions_iso_week_monday_date_locator(iso_year, iso_week) == expected_monday
        # And the Monday itself, when fed back in, must yield the same Monday.
        assert missions_iso_week_monday_date_locator(expected_monday) == expected_monday
        # Sanity-check the ISO calendar tuple too.
        assert expected_monday.isocalendar() == (iso_year, iso_week, 1)