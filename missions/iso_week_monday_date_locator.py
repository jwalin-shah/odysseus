"""
ISO Week Monday Date Locator
=============================

Provides a small helper that, given an ISO week-year and an ISO week number,
returns the calendar date of the Monday of that ISO week.

Background
----------
The ISO week date system (ISO 8601) defines:
* Weeks always start on Monday and end on Sunday.
* Week 1 of a year is the week that contains the year's first Thursday
  (equivalently, the week that contains January 4th).
* A year can have either 52 or 53 ISO weeks.

For example:
* ISO 2020, week 1  -> Monday 2019-12-30
* ISO 2021, week 1  -> Monday 2021-01-04
* ISO 2022, week 1  -> Monday 2022-01-03
* ISO 2020, week 53 -> Monday 2020-12-28  (2020 is a 53-week year)
"""

from datetime import date


def iso_week_monday_date_locator(year, week):
    """Return the date of the Monday of the given ISO week.

    Parameters
    ----------
    year : int
        The ISO week-year (e.g. 2020).  This is *not* always the same as the
        calendar year, because early-January dates may belong to the last
        ISO week of the previous year, and late-December dates may belong
        to the first ISO week of the next year.
    week : int
        The ISO week number.  Must be in the range 1..53, and must actually
        exist in the supplied ``year`` (most years only have 52 weeks).

    Returns
    -------
    datetime.date
        The date of the Monday of the requested ISO week.

    Raises
    ------
    TypeError
        If ``year`` or ``week`` is not an integer.
    ValueError
        If ``week`` is outside the 1..53 range, or if the combination of
        ``year``/``week`` does not correspond to a real ISO week.
    """
    # ---- input validation -------------------------------------------------
    if not isinstance(year, int) or isinstance(year, bool):
        raise TypeError(f"year must be int, got {type(year).__name__}")
    if not isinstance(week, int) or isinstance(week, bool):
        raise TypeError(f"week must be int, got {type(week).__name__}")
    if not (1 <= week <= 53):
        raise ValueError(
            f"ISO week number must be between 1 and 53 inclusive, got {week}"
        )

    # ---- core calculation -------------------------------------------------
    # ``date.fromisocalendar`` (Python 3.8+) is the canonical way to build
    # a date from an ISO year/week/day triple.  ISO day 1 == Monday, which
    # is exactly what we want to return.  It also correctly raises
    # ``ValueError`` for impossible combinations (e.g. week 53 in a year
    # that only has 52 weeks).
    try:
        return date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise ValueError(
            f"Week {week} does not exist in ISO year {year}"
        ) from exc


__all__ = ["iso_week_monday_date_locator"]