"""Mean Absolute Deviation around the mean.

Provides a small, dependency-free implementation of the
Mean Absolute Deviation (MAD) around the (arithmetic) mean:

    MAD = (1 / n) * sum(|x_i - mean(x)|)

The function accepts any iterable of real numbers and returns
a plain ``float``.  Edge cases (empty input, non-numeric
elements) are handled explicitly.
"""

from __future__ import annotations

from numbers import Real
from typing import Iterable


def mad_around_mean(values: Iterable[Real]) -> float:
    """Return the Mean Absolute Deviation of ``values`` around their mean.

    Parameters
    ----------
    values:
        Any iterable containing real numbers (``int`` or ``float``).
        Booleans are treated as integers and accepted.

    Returns
    -------
    float
        The mean absolute deviation.  ``0.0`` is returned for an
        empty input, since the deviation of a vacuous sample set is
        conventionally zero.

    Raises
    ------
    TypeError
        If ``values`` is not iterable, or if it contains an element
        that is not a real number.
    """
    # ``list(values)`` both materialises a generator/iterator and
    # raises ``TypeError`` if ``values`` is not iterable at all.
    values_list = list(values)
    n = len(values_list)

    if n == 0:
        return 0.0

    for v in values_list:
        # ``Real`` covers int, float, Decimal, Fraction, ... but
        # deliberately excludes ``bool``-as-Real?  Booleans are a
        # subclass of ``int`` (which is ``Real``), so the check
        # below accepts them, which matches the convention used
        # by ``statistics.mean`` and friends.
        if not isinstance(v, Real):
            raise TypeError(
                "all elements of 'values' must be real numbers, "
                f"got element of type {type(v).__name__!r}"
            )

    mean = sum(values_list) / n
    deviations = sum(abs(x - mean) for x in values_list)
    return deviations / n


__all__ = ["mad_around_mean"]