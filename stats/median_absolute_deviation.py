"""Median Absolute Deviation (MAD).

This module provides a single public function,
:func:`median_absolute_deviation`, which computes the robust
measure of statistical dispersion defined as the median of the
absolute deviations from the data's median:

    MAD = median(|x_i - median(x)|)
"""

from __future__ import annotations

from typing import Iterable, Optional


def median_absolute_deviation(
    data: Optional[Iterable],
    scale: float = 1.0,
) -> float:
    """Compute the Median Absolute Deviation of ``data``.

    Parameters
    ----------
    data : iterable, optional
        A sequence (or any iterable) of numeric values: integers,
        floats, or objects that can be converted to ``float``.
        ``None`` and an empty iterable are both treated as "no
        data" and yield ``0.0``.
    scale : float, optional
        Multiplicative scale factor applied to the result. Defaults
        to ``1.0``.  The value ``1.4826`` is the constant that makes
        the MAD a consistent estimator of the standard deviation for
        normally distributed data.

    Returns
    -------
    float
        The (possibly scaled) median absolute deviation.  ``0.0`` is
        returned for empty / ``None`` input or when every element of
        ``data`` is identical.

    Raises
    ------
    ValueError
        If ``data`` contains values that cannot be converted to
        ``float``.

    Examples
    --------
    >>> median_absolute_deviation([1, 1, 2, 2, 4, 6, 9])
    1.0
    >>> median_absolute_deviation([1, 2, 3, 4, 5, 6, 7, 8])
    2.0
    >>> median_absolute_deviation([])
    0.0
    >>> median_absolute_deviation([1, 2, 3, 4, 5], scale=1.4826)
    1.4826
    """
    # Treat "no data" gracefully: ``None`` or an empty iterable -> 0.0
    if data is None:
        return 0.0

    # Materialise the iterable and ensure every element is numeric.
    try:
        values = [float(v) for v in data]
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "data must be an iterable of numeric values"
        ) from exc

    n = len(values)
    if n == 0:
        return 0.0

    # 1) Median of the original data
    sorted_values = sorted(values)
    if n % 2 == 0:
        median_value = (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2.0
    else:
        median_value = sorted_values[n // 2]

    # 2) Absolute deviations from the median
    abs_deviations = sorted(abs(v - median_value) for v in values)

    # 3) Median of those absolute deviations
    if n % 2 == 0:
        mad = (abs_deviations[n // 2 - 1] + abs_deviations[n // 2]) / 2.0
    else:
        mad = abs_deviations[n // 2]

    return float(mad) * float(scale)


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    sample = [1, 1, 2, 2, 4, 6, 9]
    print(f"MAD({sample}) = {median_absolute_deviation(sample)}")