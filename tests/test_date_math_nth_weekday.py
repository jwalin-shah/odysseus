"""Tests for ``date_math_nth_weekday``."""

import os
import sys

import pytest
from datetime import date

# Make the ``src`` directory importable when tests are run from the repo
# root with plain ``pytest`` (no installed package, no root conftest).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "src"))

from date_math_nth_weekday import date_math_nth_weekday  # noqa: E402


# ---------------------------------------------------------------------------
# Happy-path / known dates
# ---------------------------------------------------------------------------
class TestHappyPath:
    """Well-known dates that can be verified by hand."""

    def test_first_tuesday_of_january_2024(self):
        # Jan 1, 2024 is a Monday (weekday 0).  1st Tuesday -> Jan 2.
        assert date_math_nth_weekday(2024, 1, 1, 1) == date(2024, 1, 2)

    def test_second_tuesday_of_january_2024(self):
        assert date_math_nth_weekday(2024, 1, 1, 2) == date(2024, 1, 9)

    def test_first_monday_of_january_2024(self):
        # Jan 1, 2024 is itself a Monday.
        assert date_math_nth_weekday(2024, 1, 0, 1) == date(2024, 1, 1)

    def test_third_monday_of_january_2024(self):
        # Martin Luther King Jr. Day in the US.
        assert date_math_nth_weekday(2024, 1, 0, 3) == date(2024, 1, 15)

    def test_fourth_thursday_of_november_2023_is_thanksgiving(self):
        # Thursday is weekday 3.  1st Thu of Nov 2023 is the 2nd, so the
        # 4th Thursday is the 23rd - US Thanksgiving.
        assert date_math_nth_weekday(2023, 11, 3, 4) == date(2023, 11, 23)

    def test_fifth_friday_of_december_2023(self):
        # Dec 1, 2023 is a Friday, so 5th Friday is Dec 29.
        assert date_math_nth_weekday(2023, 12, 4, 5) == date(2023, 12, 29)

    def test_first_sunday_of_february_2023(self):
        # Feb 1, 2023 is a Wednesday; 1st Sunday is Feb 5.
        assert date_math_nth_weekday(2023, 2, 6, 1) == date(2023, 2, 5)

    def test_second_wednesday_of_march_2024(self):
        # Mar 1, 2024 is a Friday; 1st Wed is Mar 6, 2nd is Mar 13.
        result = date_math_nth_weekday(2024, 3, 2, 2)
        assert result == date(2024, 3, 13)
        # And the returned date is actually a Wednesday.
        assert result.weekday() == 2

    def test_fourth_tuesday_of_february_2024_leap_year(self):
        # 2024 is a leap year.  Feb 1 is a Thursday; 1st Tue is Feb 6,
        # 4th Tue is Feb 27.
        assert date_math_nth_weekday(2024, 2, 1, 4) == date(2024, 2, 27)

    def test_first_monday_of_january_2025(self):
        # Jan 1, 2025 is a Wednesday; 1st Monday is Jan 6.
        assert date_math_nth_weekday(2025, 1, 0, 1) == date(2025, 1, 6)

    def test_third_sunday_of_july_2024(self):
        # Jul 1, 2024 is a Monday; 1st Sun is Jul 7, 3rd Sun is Jul 21.
        assert date_math_nth_weekday(2024, 7, 6, 3) == date(2024, 7, 21)


# ---------------------------------------------------------------------------
# Return type guarantees
# ---------------------------------------------------------------------------
class TestReturnType:
    def test_returns_date_instance(self):
        result = date_math_nth_weekday(2024, 1, 1, 1)
        assert isinstance(result, date)

    def test_returned_date_has_correct_attributes(self):
        result = date_math_nth_weekday(2024, 1, 1, 1)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 2

    def test_returned_date_is_actually_the_requested_weekday(self):
        # Run a battery of random-ish lookups and check the result's weekday.
        for year, month, weekday, n in [
            (2020, 5, 0, 2),   # 2nd Monday of May 2020
            (2021, 8, 2, 3),   # 3rd Wednesday of Aug 2021
            (2022, 11, 4, 4),  # 4th Friday of Nov 2022
            (2023, 3, 6, 1),   # 1st Sunday of Mar 2023
            (2024, 6, 5, 5),   # 5th Saturday of Jun 2024
        ]:
            result = date_math_nth_weekday(year, month, weekday, n)
            assert result.weekday() == weekday, (
                f"Expected weekday {weekday}, got {result.weekday()} "
                f"for {year}-{month:02d} occurrence {n}"
            )


# ---------------------------------------------------------------------------
# Occurrences that don't fit in the month
# ---------------------------------------------------------------------------
class TestImpossibleOccurrences:
    """nth occurrences that don't fit in the month must raise ``ValueError``."""

    def test_fifth_monday_missing_in_february_2023(self):
        # Feb 2023 has 28 days; the 5th Monday would land on Mar 6.
        with pytest.raises(ValueError):
            date_math_nth_weekday(2023, 2, 0, 5)

    def test_fifth_friday_missing_in_february_2024(self):
        # Feb 2024 is a leap year with 29 days.  1st Fri is Feb 2,
        # 5th Fri would be Mar 2 - out of range.
        with pytest.raises(ValueError):
            date_math_nth_weekday(2024, 2, 4, 5)

    def test_error_message_mentions_month_and_year(self):
        with pytest.raises(ValueError) as excinfo:
            date_math_nth_weekday(2023, 2, 0, 5)
        message = str(excinfo.value)
        assert "February" in message
        assert "2023" in message


# ---------------------------------------------------------------------------
# Argument validation
# ---------------------------------------------------------------------------
class TestInvalidInputs:
    @pytest.mark.parametrize("month", [0, -1, 13, 100])
    def test_bad_month_raises(self, month):
        with pytest.raises(ValueError):
            date_math_nth_weekday(2024, month, 0, 1)

    @pytest.mark.parametrize("weekday", [-1, 7, 10])
    def test_bad_weekday_raises(self, weekday):
        with pytest.raises(ValueError):
            date_math_nth_weekday(2024, 1, weekday, 1)

    @pytest.mark.parametrize("n", [0, -1, 6, 100])
    def test_bad_n_raises(self, n):
        with pytest.raises(ValueError):
            date_math_nth_weekday(2024, 1, 0, n)

    @pytest.mark.parametrize("bad", ["2024", 1.0, None, True, False, [1], (1,)])
    def test_non_integer_arguments_raise_type_error(self, bad):
        # Every positional argument must be a real ``int``.
        with pytest.raises(TypeError):
            date_math_nth_weekday(bad, 1, 0, 1)
        with pytest.raises(TypeError):
            date_math_nth_weekday(2024, bad, 0, 1)
        with pytest.raises(TypeError):
            date_math_nth_weekday(2024, 1, bad, 1)
        with pytest.raises(TypeError):
            date_math_nth_weekday(2024, 1, 0, bad)