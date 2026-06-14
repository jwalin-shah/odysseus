"""Compact human-readable duration formatting.

Converts a duration expressed in seconds into a compact string such as
``"1d 2h 3m 4s"``. Only non-zero units are emitted, and ``0`` always
renders as ``"0s"``.
"""

from __future__ import annotations

# Seconds contained in each unit we know about.
_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 60 * _SECONDS_PER_MINUTE
_SECONDS_PER_DAY = 24 * _SECONDS_PER_HOUR


def compact_duration(seconds):
    """Return a compact, human-readable representation of *seconds*.

    The input is interpreted as a non-negative number of seconds.
    Floating-point values are truncated toward zero. The output contains
    only the non-zero components, joined by a single space, using the
    suffixes ``d``, ``h``, ``m`` and ``s`` for days, hours, minutes and
    seconds respectively. ``0`` always returns ``"0s"``.

    Parameters
    ----------
    seconds:
        A non-negative real number of seconds. May be ``int`` or ``float``.

    Returns
    -------
    str
        A compact representation such as ``"1d 2h 3m 4s"``.

    Raises
    ------
    TypeError
        If ``seconds`` is not a real number (booleans are rejected
        because they are a subclass of ``int``).
    ValueError
        If ``seconds`` is negative.
    """
    # ``bool`` is a subclass of ``int``; we don't want to accept it.
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        raise TypeError("seconds must be a real number")
    if seconds != seconds:  # NaN check that works for both int and float.
        raise ValueError("seconds must be a finite number")
    if seconds < 0:
        raise ValueError("seconds must be non-negative")

    total = int(seconds)
    if total == 0:
        return "0s"

    days, remainder = divmod(total, _SECONDS_PER_DAY)
    hours, remainder = divmod(remainder, _SECONDS_PER_HOUR)
    minutes, secs = divmod(remainder, _SECONDS_PER_MINUTE)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs:
        parts.append(f"{secs}s")

    return " ".join(parts)