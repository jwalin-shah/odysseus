"""
Linear interval rescaler for interval-math style mapping.

Provides a single function, ``interval_math_linear_interval_rescaler``,
that linearly maps a value from a source interval ``[src_lo, src_hi]`` to
a target interval ``[tgt_lo, tgt_hi]``.

The mapping is the standard linear interpolation / extrapolation formula

    y = tgt_lo + (x - src_lo) * (tgt_hi - tgt_lo) / (src_hi - src_lo)

so the lower source bound maps to the lower target bound, the upper
source bound maps to the upper target bound, and every interior point
is mapped proportionally.  Values outside the source interval are
extrapolated linearly, which is the usual behaviour for a "rescaler".
"""

from __future__ import annotations

from numbers import Real
from typing import Union

Number = Union[int, float]


def interval_math_linear_interval_rescaler(
    value: Number,
    src_lo: Number,
    src_hi: Number,
    tgt_lo: Number,
    tgt_hi: Number,
) -> float:
    """Linearly rescale ``value`` from ``[src_lo, src_hi]`` to ``[tgt_lo, tgt_hi]``.

    Parameters
    ----------
    value:
        The scalar value to be rescaled.  It does not need to lie inside
        the source interval; values outside are extrapolated linearly.
    src_lo, src_hi:
        Bounds of the source interval.  ``src_lo`` is mapped onto
        ``tgt_lo`` and ``src_hi`` onto ``tgt_hi``.
    tgt_lo, tgt_hi:
        Bounds of the target interval.

    Returns
    -------
    float
        The value mapped into the target interval.

    Notes
    -----
    A degenerate source interval (``src_hi == src_lo``) has no defined
    width, so a unique linear map cannot be constructed.  In that case
    the function returns the midpoint of the target interval, which is
    the only value-independent choice that treats the source point
    symmetrically.

    Raises
    ------
    TypeError
        If any of the arguments is not a real number.
    """
    for name, arg in (
        ("value", value),
        ("src_lo", src_lo),
        ("src_hi", src_hi),
        ("tgt_lo", tgt_lo),
        ("tgt_hi", tgt_hi),
    ):
        if not isinstance(arg, Real) or isinstance(arg, bool):
            raise TypeError(
                f"{name!r} must be a real number, got {type(arg).__name__}"
            )

    span = src_hi - src_lo
    if span == 0:
        # Degenerate source interval: there is no unique linear map.
        # Fall back to the midpoint of the target interval, which is
        # symmetric in tgt_lo / tgt_hi and value-independent.
        return (float(tgt_lo) + float(tgt_hi)) / 2.0

    scale = (tgt_hi - tgt_lo) / span
    return float(tgt_lo + (value - src_lo) * scale)


__all__ = ["interval_math_linear_interval_rescaler"]