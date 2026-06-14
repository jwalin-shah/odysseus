"""Interquartile mean (IQM) computation.

The interquartile mean is a robust measure of central tendency that
discards the lowest and highest 25% of values before computing the
arithmetic mean.  It is equivalent to
``scipy.stats.trim_mean(data, 0.25)``.
"""
from __future__ import annotations

from typing import Sequence, Union

Number = Union[int, float]


def interquartile_mean(data: Sequence[Number]) -> float:
    """Compute the interquartile mean of a sequence of numbers.

    The interquartile mean (IQM) is calculated by:

        1. Sorting the values in ascending order.
        2. Removing the lowest 25% and highest 25% of values.
        3. Computing the arithmetic mean of the remaining values.

    The number of values removed from each end is ``floor(n / 4)``
    where ``n`` is the length of ``data``.  When ``n < 4`` no values
    are trimmed and the result is simply the arithmetic mean of the
    input.

    Args:
        data: A non-empty sequence of numeric values (``int`` or
            ``float``).

    Returns:
        The interquartile mean as a ``float``.

    Raises:
        ValueError: If ``data`` is empty or ``None``.
        TypeError: If ``data`` contains values that cannot be
            compared or summed.

    Examples:
        >>> interquartile_mean([1, 2, 3, 4, 5, 6, 7, 8])
        4.5
        >>> interquartile_mean([1, 5, 9])
        5.0
    """
    if data is None:
        raise ValueError("data must not be None")

    try:
        sorted_data = sorted(data)
    except TypeError as exc:
        raise TypeError(
            "data must contain comparable numeric values"
        ) from exc

    n = len(sorted_data)
    if n == 0:
        raise ValueError("data must be a non-empty sequence")

    # Number of values to trim from each end.
    k = n // 4
    trimmed = sorted_data[k:n - k] if k > 0 else sorted_data

    if not trimmed:
        # Defensive fallback - cannot actually occur for non-empty input,
        # but guards against pathological Sequence subclasses.
        return float(sorted_data[n // 2])

    return float(sum(trimmed)) / len(trimmed)