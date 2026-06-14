"""Winsorized mean calculation utility.

The winsorized mean is a robust measure of central tendency that limits
the influence of extreme values by replacing the smallest and largest
values in a dataset with the nearest remaining values before computing
the arithmetic mean.
"""
from __future__ import annotations

import math
from typing import Iterable, Union

Number = Union[int, float]


def winsorized_mean(data: Iterable[Number], limit: float = 0.2) -> float:
    """Calculate the winsorized mean of a numeric sequence.

    Parameters
    ----------
    data : iterable of numbers
        The values to average.
    limit : float, optional
        Fraction of values to winsorize from each tail. Must satisfy
        ``0 <= limit <= 0.5``. Default is 0.2 (20%).

    Returns
    -------
    float
        The winsorized mean.

    Raises
    ------
    TypeError
        If ``data`` is not iterable, is a string, or contains non-numeric
        elements (including ``None`` and ``bool``).
    ValueError
        If ``data`` is empty, ``limit`` is outside ``[0, 0.5]``, or any
        element is NaN or infinite.
    """
    if isinstance(data, (str, bytes)):
        raise TypeError(
            "data must be an iterable of numbers, not a string"
        )

    try:
        iterator = iter(data)
    except TypeError as exc:
        raise TypeError("data must be iterable") from exc

    values: list[float] = []
    for item in iterator:
        # Reject booleans explicitly because bool is a subclass of int.
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(
                f"all elements must be numeric, got {type(item).__name__}"
            )
        f = float(item)
        if math.isnan(f) or math.isinf(f):
            raise ValueError("elements must be finite numbers")
        values.append(f)

    if not values:
        raise ValueError("data must not be empty")

    if isinstance(limit, bool) or not isinstance(limit, (int, float)):
        raise TypeError("limit must be numeric")
    if limit < 0 or limit > 0.5:
        raise ValueError("limit must be in the range [0, 0.5]")

    n = len(values)
    k = int(limit * n)
    sorted_values = sorted(values)

    if k == 0:
        return sum(sorted_values) / n

    replacement_low = sorted_values[k]
    replacement_high = sorted_values[n - k - 1]

    winsorized = list(sorted_values)
    for i in range(k):
        winsorized[i] = replacement_low
        winsorized[n - 1 - i] = replacement_high

    return sum(winsorized) / n