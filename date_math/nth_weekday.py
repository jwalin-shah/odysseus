from datetime import date


def nth_weekday(year, month, weekday, n):
    """Return the date of the nth occurrence of a weekday in a month.

    Args:
        year:   The calendar year.
        month:  The month, 1-12.
        weekday: The day of the week using Python's ``date.weekday()``
                 convention (0=Monday, 1=Tuesday, ..., 6=Sunday).
        n:      Which occurrence to return, 1-based. Must be >= 1.

    Returns:
        The ``datetime.date`` of the nth ``weekday`` in the given month.

    Raises:
        ValueError: If ``month`` is not in 1..12, ``weekday`` is not in
                    0..6, ``n`` is not a positive integer, or the nth
                    occurrence does not exist within the month.
    """
    if not isinstance(month, int) or not (1 <= month <= 12):
        raise ValueError(f"month must be an integer in 1..12, got {month!r}")
    if not isinstance(weekday, int) or not (0 <= weekday <= 6):
        raise ValueError(f"weekday must be an integer in 0..6, got {weekday!r}")
    if not isinstance(n, int) or n < 1:
        raise ValueError(f"n must be a positive integer, got {n!r}")

    first_day = date(year, month, 1)

    # Days from the 1st of the month to the first requested weekday.
    days_until = (weekday - first_day.weekday()) % 7
    first_occurrence_day = 1 + days_until

    # Advance (n - 1) full weeks to land on the nth occurrence.
    target_day = first_occurrence_day + (n - 1) * 7

    try:
        return date(year, month, target_day)
    except ValueError:
        # ``date`` raises ValueError when the day is out of range for the
        # month, which is exactly the "doesn't exist" condition we want
        # to surface to the caller.
        raise ValueError(
            f"The {n}th occurrence of weekday {weekday} does not exist "
            f"in {year}-{month:02d}"
        ) from None