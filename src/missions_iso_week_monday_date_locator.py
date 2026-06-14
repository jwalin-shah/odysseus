"""
missions_iso_week_monday_date_locator
=====================================

Locate the Monday date of an ISO 8601 week.

ISO weeks (per ISO 8601) always start on a Monday. Week 1 of an ISO year is
the week that contains the first Thursday of the Gregorian year (equivalently,
the week containing January 4th). Most years have 52 ISO weeks; years that
begin on a Thursday (or leap years that begin on a Wednesday) have 53.

This module exposes a single helper, ``missions_iso_week_monday_date_locator``,
which supports two natural calling patterns:

1. Pass a ``date`` (or ``datetime``) and receive the Monday of the ISO week
   that contains that date.
2. Pass an ``(iso_year, iso_week)`` pair and receive the Monday of that ISO
   week directly.

Edge cases handled:

* Dates that straddle a Gregorian year boundary but belong to the previous or
  next ISO year (e.g. 2023-01-01 is in ISO 2022-W52; 2024-12-31 is in
  ISO 2025-W01).
* ISO week 53 which only exists in certain years (``ValueError`` otherwise).
* Invalid week numbers (< 1 or > 53) and unsupported argument types.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Union


DateLike = Union[date, datetime]
YearInt = int
WeekInt = int

__all__ = ["missions_iso_week_monday_date_locator"]


def _coerce_to_date(value: DateLike) -> date:
    """Return the date portion of a ``date`` or ``datetime`` instance."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raise TypeError(
        f"Expected a datetime.date or datetime.datetime instance, "
        f"got {type(value).__name__!s}"
    )


def _monday_for_iso_week(iso_year: int, iso_week: int) -> date:
    """Return the Monday (date) of the given ISO year/week, validating inputs."""
    if not isinstance(iso_year, int) or isinstance(iso_year, bool):
        raise TypeError(f"iso_year must be an int, got {type(iso_year).__name__!s}")
    if not isinstance(iso_week, int) or isinstance(iso_week, bool):
        raise TypeError(f"iso_week must be an int, got {type(iso_week).__name__!s}")
    if iso_week < 1 or iso_week > 53:
        raise ValueError(
            f"iso_week must be between 1 and 53 (inclusive), got {iso_week}"
        )

    # ``date.fromisocalendar`` will raise ValueError if the week does not
    # exist for the given year (e.g. asking for week 53 of a 52-week year).
    try:
        return date.fromisocalendar(iso_year, iso_week, 1)  # 1 == Monday
    except ValueError as exc:
        raise ValueError(
            f"ISO week {iso_week} does not exist in year {iso_year}"
        ) from exc


def missions_iso_week_monday_date_locator(
    year_or_date: Union[YearInt, DateLike],
    week: WeekInt = None,
) -> date:
    """
    Locate the Monday date of an ISO week.

    Two calling conventions are supported.

    Convention A — locate the Monday of the ISO week that contains a date::

        >>> missions_iso_week_monday_date_locator(date(2024, 1, 10))
        datetime.date(2024, 1, 8)

    Convention B — locate the Monday of an explicit ISO year/week pair::

        >>> missions_iso_week_monday_date_locator(2024, 1)
        datetime.date(2024, 1, 1)

    :param year_or_date: Either a ``datetime.date`` / ``datetime.datetime``
        instance (Convention A), or an ``int`` ISO year (Convention B).
    :param week: An ``int`` ISO week number (1..53). Required for
        Convention B; must be omitted (or ``None``) for Convention A.
    :returns: A ``datetime.date`` representing the Monday of the resolved
        ISO week.
    :raises TypeError: If the argument types are unsupported, or if
        Convention B is used without an integer week.
    :raises ValueError: If the ISO week is out of range or does not exist
        for the given year.
    """
    # Convention A: a date-like was passed.
    if isinstance(year_or_date, (date, datetime)):
        if week is not None and not (
            isinstance(week, int) and not isinstance(week, bool)
        ):
            raise TypeError(
                "When passing a date, the 'week' argument must be omitted."
            )
        target = _coerce_to_date(year_or_date)
        iso_year, iso_week, _ = target.isocalendar()
        return _monday_for_iso_week(iso_year, iso_week)

    # Convention B: an integer year was passed.
    if isinstance(year_or_date, int) and not isinstance(year_or_date, bool):
        if week is None:
            raise ValueError(
                "When passing a year, an ISO week number must also be provided."
            )
        return _monday_for_iso_week(year_or_date, week)

    raise TypeError(
        "First argument must be a datetime.date / datetime.datetime, "
        f"or an int ISO year; got {type(year_or_date).__name__!s}."
    )