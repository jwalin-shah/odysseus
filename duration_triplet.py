"""
duration_triplet.py

Provides the `duration_triplet` utility for converting a duration
expressed in seconds into a (hours, minutes, seconds) triplet.
"""


def duration_triplet(seconds):
    """Convert a duration in seconds to a (hours, minutes, seconds) triplet.

    Parameters
    ----------
    seconds : int or float
        The duration in seconds. May be a whole number or a fractional value.
        Negative values are not allowed.

    Returns
    -------
    tuple of (int, int, int)
        A triplet ``(hours, minutes, secs)`` where each component is a
        non-negative integer. The fractional part of ``seconds`` is truncated.

    Raises
    ------
    TypeError
        If ``seconds`` is not a real number.
    ValueError
        If ``seconds`` is negative.

    Examples
    --------
    >>> duration_triplet(3661)
    (1, 1, 1)
    >>> duration_triplet(0)
    (0, 0, 0)
    >>> duration_triplet(45.9)
    (0, 0, 45)
    """
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool):
        raise TypeError("seconds must be a real number (int or float)")
    if seconds < 0:
        raise ValueError("seconds must be non-negative")

    total = int(seconds)  # truncate fractional part
    hours = total // 3600
    remainder = total % 3600
    minutes = remainder // 60
    secs = remainder % 60
    return (hours, minutes, secs)


if __name__ == "__main__":
    # Simple smoke test when run directly.
    samples = [0, 1, 59, 60, 3599, 3600, 3661, 7325, 100.7]
    for s in samples:
        print(f"{s}s -> {duration_triplet(s)}")