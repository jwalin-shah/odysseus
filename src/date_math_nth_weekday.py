"""Calculate the date of the nth occurrence of a specific weekday in a month."""

import calendar
from datetime import date


def date_math_nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """Return the date of the *n* th occurrence of a given weekday in a month.

    Parameters
    ----------
    year : int
        The four-digit year (e.g. ``2024``).
    month : int
        The month, ``1`` (January) through ``12`` (December).
    weekday : int
        The day of the week, ``0`` (Monday) through ``6`` (Sunday), matching
        :meth:`datetime.date.weekday`.
    n : int
        Which occurrence to return, ``1`` (first) through ``5`` (fifth).
        ``5`` is the maximum any weekday can possibly occur in a single
        month.

    Returns
    -------
    datetime.date
        The :class:`datetime.date` of the *n* th ``weekday`` in the
        requested ``year`` / ``month``.

    Raises
    ------
    TypeError
        If any of the arguments is not an ``int`` (this includes
        ``bool``, which is technically a subclass of ``int`` in Python).
    ValueError
        If ``month`` is not in ``1..12``, ``weekday`` is not in ``0..6``,
        ``n`` is not in ``1..5``, or the requested *n* th occurrence
        does not exist in the month (for example, the 5th Monday of a
        28-day February).

    Examples
    --------
    >>> date_math_nth_weekday(2024, 1, 1, 1)   # 1st Tuesday of Jan 2024
    datetime.date(2024, 1, 2)
    >>> date_math_nth_weekday(2023, 11, 3, 4)  # US Thanksgiving 2023
    datetime.date(2023, 11, 23)
    """
    # ---- input validation ------------------------------------------------
    # ``bool`` is a subclass of ``int`` in Python; reject it explicitly so
    # that ``True`` / ``False`` are not silently coerced to ``1`` / ``0``.
    for name, value in (("year", year), ("month", month),
                        ("weekday", weekday), ("n", n)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                f"{name} must be an int, got {type(value).__name__}"
            )

    if not 1 <= month <= 12:
        raise ValueError(f"month must be between 1 and 12, got {month}")
    if not 0 <= weekday <= 6:
        raise ValueError(
            f"weekday must be between 0 (Monday) and 6 (Sunday), got {weekday}"
        )
    if not 1 <= n <= 5:
        raise ValueError(f"n must be between 1 and 5, got {n}")

    # ---- core calculation ------------------------------------------------
    first_of_month = date(year, month, 1)

    # How many days from the 1st of the month until the first requested
    # weekday?  ``% 7`` wraps the negative case (when the target weekday
    # is earlier in the week than the month's first day).
    days_until_target = (weekday - first_of_month.weekday()) % 7
    first_occurrence_day = 1 + days_until_target
    target_day = first_occurrence_day + (n - 1) * 7

    # The 5th occurrence of any weekday requires at least 29 days
    # (``1 + 4 * 7 = 29``).  For shorter months it simply cannot exist.
    days_in_month = calendar.monthrange(year, month)[1]
    if target_day > days_in_month:
        raise ValueError(
            f"There is no {n}th occurrence of weekday {weekday} "
            f"in {calendar.month_name[month]} {year}"
        )

    return date(year, month, target_day)