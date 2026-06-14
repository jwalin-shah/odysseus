"""Mean Absolute Deviation (MAD) around the mean.

The Mean Absolute Deviation around the mean is a measure of dispersion
that quantifies the average absolute distance of each data point from
the arithmetic mean of the dataset.

    MAD = (1 / n) * sum(|x_i - mean(x)|)

This module exposes a single public function: :func:`stats_mad_around_mean`.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Union

Number = Union[int, float]


def _coerce_to_list(data: Iterable[Number]) -> List[Number]:
    """Validate and coerce the input to a plain ``list`` of numbers.

    Parameters
    ----------
    data:
        Any iterable of numeric values.

    Returns
    -------
    list
        A list containing the numeric values from ``data``.

    Raises
    ------
    TypeError
        If ``data`` is not iterable, or if any element is not a real
        number (``int`` or ``float``, but not ``bool`` to avoid subtle
        semantic bugs in downstream numeric code).
    """
    if isinstance(data, (str, bytes, dict)):
        raise TypeError(
            f"data must be an iterable of numbers, got {type(data).__name__}"
        )
    try:
        iterator = iter(data)
    except TypeError as exc:
        raise TypeError(
            f"data must be an iterable of numbers, got {type(data).__name__}"
        ) from exc

    values: List[Number] = []
    for index, item in enumerate(iterator):
        # Reject bool explicitly; bool is a subclass of int but rarely
        # what callers want when computing descriptive statistics.
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(
                f"data[{index}] must be a real number, got {type(item).__name__}"
            )
        values.append(item)
    return values


def stats_mad_around_mean(data: Iterable[Number]) -> float:
    """Compute the Mean Absolute Deviation (MAD) around the mean.

    Parameters
    ----------
    data:
        An iterable of numeric values (``int`` or ``float``).

    Returns
    -------
    float
        The mean absolute deviation of the values from their arithmetic
        mean. Returns ``0.0`` for an empty sequence, which is a sensible
        neutral element (the deviation of an empty population is zero).

    Raises
    ------
    TypeError
        If ``data`` is not iterable, or contains non-numeric values.

    Examples
    --------
    >>> stats_mad_around_mean([1, 2, 3, 4, 5])
    1.2
    >>> stats_mad_around_mean([5, 5, 5])
    0.0
    >>> stats_mad_around_mean([])
    0.0
    """
    values = _coerce_to_list(data)

    n = len(values)
    if n == 0:
        return 0.0

    mean = sum(values) / n
    mad = sum(abs(x - mean) for x in values) / n
    return float(mad)


__all__ = ["stats_mad_around_mean"]


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    sample = [1, 2, 3, 4, 5]
    print(f"MAD of {sample} = {stats_mad_around_mean(sample)}")