"""ordinal_day_module — utilities for working with ordinal days of the year.

An "ordinal day" (or "day of year") is the position of a calendar date within
its year, ranging from 1 (January 1st) to 365 in a common year and 366 in a
leap year (December 31st).

The module exposes three public helpers:

* :func:`is_leap_year` — determine whether a given year is a leap year.
* :func:`ordinal_day`  — convert a :class:`datetime.date` (or
  :class:`datetime.datetime`) to its ordinal day number.
* :func:`from_ordinal_day` — inverse operation: build a date from a
  ``(year, ordinal)`` pair.

All functions are pure, side-effect free, and validate their inputs.
"""

from datetime import date, datetime
from typing import Union

__all__ = ["is_leap_year", "ordinal_day", "from_ordinal_day"]

DateLike = Union[date, datetime]


def is_leap_year(year: int) -> bool:
    """Return ``True`` if ``year`` is a leap year, ``False`` otherwise.

    A year is a leap year if it is divisible by 4, *except* years that are
    divisible by 100 — those are leap years only if they are also divisible
    by 400.
    """
    if not isinstance(year, int) or isinstance(year, bool):
        raise TypeError(f"is_leap_year expected int, got {type(year).__name__}")
    return (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)


def ordinal_day(value: DateLike) -> int:
    """Return the ordinal day of the year (1..366) for ``value``.

    Parameters
    ----------
    value:
        A :class:`datetime.date` or :class:`datetime.datetime` instance.

    Returns
    -------
    int
        The day of the year.  January 1st → 1, December 31st → 365 (or
        366 in a leap year).

    Raises
    ------
    TypeError
        If ``value`` is not a ``date`` or ``datetime``.
    """
    if isinstance(value, datetime):
        value = value.date()
    if not isinstance(value, date):
        raise TypeError(
            "ordinal_day expected datetime.date or datetime.datetime, "
            f"got {type(value).__name__}"
        )
    # ``timetuple().tm_yday`` is the day of year, 1..366.
    return value.timetuple().tm_yday


def from_ordinal_day(year: int, ordinal: int) -> date:
    """Return the :class:`date` corresponding to ``ordinal`` inside ``year``.

    Parameters
    ----------
    year:
        The calendar year (e.g. ``2024``).
    ordinal:
        The day-of-year, ``1..365`` for a common year and ``1..366`` for a
        leap year.

    Returns
    -------
    datetime.date
        The matching calendar date.

    Raises
    ------
    TypeError
        If ``year`` or ``ordinal`` is not an ``int``.
    ValueError
        If ``ordinal`` is outside the valid range for ``year``.
    """
    if not isinstance(year, int) or isinstance(year, bool):
        raise TypeError(f"year must be int, got {type(year).__name__}")
    if not isinstance(ordinal, int) or isinstance(ordinal, bool):
        raise TypeError(f"ordinal must be int, got {type(ordinal).__name__}")

    max_day = 366 if is_leap_year(year) else 365
    if ordinal < 1 or ordinal > max_day:
        raise ValueError(
            f"ordinal {ordinal} is out of range for year {year} "
            f"(valid range: 1..{max_day})"
        )
    # ``date.fromordinal`` counts days from Jan 1 of year 1; adding
    # ``ordinal - 1`` to Jan 1 of ``year`` gives the right date.
    jan_first = date(year, 1, 1)
    return date.fromordinal(jan_first.toordinal() + ordinal - 1)