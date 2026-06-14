"""Jaccard similarity between two 1-D intervals.

The Jaccard index (a.k.a. Jaccard similarity coefficient) is a standard
statistic for measuring the overlap between two sets:

    J(A, B) = |A ∩ B| / |A ∪ B|

For 1-D closed intervals, the "size" of an interval is its length on the
real line, ``end - start``.  This module provides a small, dependency-free
implementation that also gracefully handles the degenerate (zero-length)
case.
"""

from typing import Sequence, Union

Interval = Union[Sequence[float], Sequence[int]]


def interval_jaccard(a: Interval, b: Interval) -> float:
    """Return the Jaccard similarity between two closed intervals.

    Each interval is given as a 2-element sequence ``(start, end)`` with
    ``start <= end``.  The returned value is in ``[0.0, 1.0]``.

    Conventions
    -----------
    * Identical intervals yield ``1.0``.
    * Disjoint intervals yield ``0.0``.
    * Two zero-length intervals at the same point yield ``1.0`` (they
      represent the same singleton set); at different points they yield
      ``0.0``.
    * A zero-length interval fully inside a positive-length interval
      yields ``1.0``; outside, ``0.0``.

    Parameters
    ----------
    a, b : (start, end)
        The two intervals to compare.

    Returns
    -------
    float
        The Jaccard similarity in ``[0.0, 1.0]``.

    Raises
    ------
    ValueError
        If either interval is malformed (``start > end``).
    TypeError
        If the inputs cannot be unpacked as 2-element sequences.

    Examples
    --------
    >>> interval_jaccard((0, 10), (0, 10))
    1.0
    >>> interval_jaccard((0, 10), (5, 15))
    0.3333333333333333
    >>> interval_jaccard((0, 5), (10, 15))
    0.0
    """
    # --- Validate & unpack -------------------------------------------------
    try:
        a_start, a_end = a
        b_start, b_end = b
    except (TypeError, ValueError):
        raise TypeError(
            "Intervals must be 2-element sequences (start, end); "
            f"got a={a!r}, b={b!r}"
        )

    if a_start > a_end or b_start > b_end:
        raise ValueError(
            f"Invalid interval: start must be <= end (got a={a!r}, b={b!r})"
        )

    # --- Degenerate (zero-length) handling ---------------------------------
    a_len = a_end - a_start
    b_len = b_end - b_start

    # Both intervals are points.
    if a_len == 0 and b_len == 0:
        return 1.0 if a_start == b_start else 0.0

    # Exactly one interval is a point: it's a hit only if it lies inside
    # the other interval.
    if a_len == 0:
        return 1.0 if b_start <= a_start <= b_end else 0.0
    if b_len == 0:
        return 1.0 if a_start <= b_start <= a_end else 0.0

    # --- General case: both intervals have positive length -----------------
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = a_len + b_len - inter

    # Defensive guard for the (numerically) zero-union case.
    if union <= 0:
        return 1.0

    return inter / union