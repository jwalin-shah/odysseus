from datetime import date


def iso_week_to_monday(year, week):
    """
    Convert an ISO 8601 week date (year, week) to the date of the Monday
    of that week.

    In the ISO 8601 calendar:
      * Weeks start on Monday (weekday 1).
      * Week 1 of a year is the week containing the year's first Thursday
        (equivalently, January 4th).
      * A year has either 52 or 53 ISO weeks.

    Parameters
    ----------
    year : int
        The ISO year.
    week : int
        The ISO week number (1-53).

    Returns
    -------
    datetime.date
        The calendar date of the Monday of the requested ISO week.

    Raises
    ------
    TypeError
        If ``year`` or ``week`` is not an integer.
    ValueError
        If ``week`` is not a valid ISO week number for the given year.
    """
    # Explicit type checking. ``bool`` is a subclass of ``int`` in Python, so
    # reject it explicitly to avoid silently turning ``True``/``False`` into
    # ``1``/``0``.
    if not isinstance(year, int) or isinstance(year, bool):
        raise TypeError(
            "year must be an int, got {}".format(type(year).__name__)
        )
    if not isinstance(week, int) or isinstance(week, bool):
        raise TypeError(
            "week must be an int, got {}".format(type(week).__name__)
        )

    # Broad range check. The stricter, per-year check is performed by
    # ``date.fromisocalendar`` below (e.g. it rejects W53 for a 52-week year).
    if week < 1 or week > 53:
        raise ValueError("week must be between 1 and 53, got {}".format(week))

    # ISO weekday 1 == Monday.
    return date.fromisocalendar(year, week, 1)