"""Gini coefficient calculation.

The Gini coefficient (Gini index) is a measure of statistical dispersion
representing inequality in a distribution. It is commonly used in
economics to measure income or wealth inequality.

A value of 0 indicates perfect equality (every value is the same);
a value approaching 1 indicates maximum inequality (one value holds
everything while the rest hold nothing).
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Union

Number = Union[int, float]


def gini(values: Sequence[Number]) -> float:
    """Compute the Gini coefficient of a sequence of non-negative numbers.

    The implementation uses the standard sorted-values formula:

        G = (2 * sum_i (i * x_sorted[i])) / (n * sum(x)) - (n + 1) / n

    Args:
        values: A non-empty list or tuple of non-negative numbers.
                Order does not affect the result.

    Returns:
        The Gini coefficient as a float in the range [0, 1].

    Raises:
        TypeError: If ``values`` is not a list/tuple, or if any element
            cannot be converted to a number.
        ValueError: If ``values`` is empty or contains negative numbers.
    """
    if not isinstance(values, (list, tuple)):
        raise TypeError(
            "values must be a list or tuple of numbers, got "
            f"{type(values).__name__}"
        )

    n = len(values)
    if n == 0:
        raise ValueError("values cannot be empty")

    # Convert to floats, validating types along the way.
    numeric: List[float] = []
    for item in values:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(
                f"all values must be numeric, got {type(item).__name__}: {item!r}"
            )
        numeric.append(float(item))

    if any(v < 0 for v in numeric):
        raise ValueError("values must be non-negative")

    # A single value, or a list of all-equal values, has Gini = 0 by convention.
    if n == 1:
        return 0.0

    total = sum(numeric)
    if total == 0.0:
        # All zeros -> perfect equality.
        return 0.0

    sorted_values = sorted(numeric)
    weighted_sum = 0.0
    for i, v in enumerate(sorted_values, start=1):
        weighted_sum += i * v

    g = (2.0 * weighted_sum) / (n * total) - (n + 1.0) / n

    # Numerical safety: clip to [0, 1] to absorb tiny floating-point
    # overshoots, but never return a value that is clearly wrong.
    if g < 0.0:
        return 0.0
    if g > 1.0:
        return 1.0
    return g


__all__ = ["gini"]