"""Linear interval rescaling utility.

This module exposes :func:`linear_interval_rescaler`, which returns a callable
that maps values from one numeric interval onto another using a linear
transformation.

Given a source interval ``[lo, hi]`` and a target interval ``[new_min, new_max]``,
the returned function ``f`` satisfies::

    f(lo)   == new_min
    f(hi)   == new_max
    f(x)    == new_min + (x - lo) * (new_max - new_min) / (hi - lo)
"""

from __future__ import annotations

from numbers import Real
from typing import Callable, Sequence


def linear_interval_rescaler(
    interval: Sequence[Real],
    new_min: Real = 0.0,
    new_max: Real = 1.0,
) -> Callable[[Real], Real]:
    """Build a callable that linearly rescales values from ``interval`` to ``[new_min, new_max]``.

    Parameters
    ----------
    interval
        A two-element sequence ``(lo, hi)`` describing the source interval.
    new_min
        Lower bound of the target interval. Defaults to ``0.0``.
    new_max
        Upper bound of the target interval. Defaults to ``1.0``.

    Returns
    -------
    callable
        A function that accepts a single numeric value ``x`` and returns the
        linearly rescaled value.

    Raises
    ------
    ValueError
        If ``interval`` is not a two-element sequence of real numbers, the
        interval has zero width, or ``new_min``/``new_max`` are not real
        numbers.
    """
    # --- Validate the interval argument -----------------------------------
    if not isinstance(interval, (list, tuple)):
        raise ValueError("interval must be a list or tuple of two numbers")
    if len(interval) != 2:
        raise ValueError("interval must contain exactly two elements")
    lo, hi = interval
    if not isinstance(lo, Real) or not isinstance(hi, Real):
        raise ValueError("interval bounds must be real numbers")
    if lo != lo or hi != hi:  # NaN check
        raise ValueError("interval bounds must not be NaN")
    if lo == hi:
        raise ValueError("interval must have non-zero width")

    # --- Validate the target bounds ---------------------------------------
    if not isinstance(new_min, Real) or not isinstance(new_max, Real):
        raise ValueError("new_min and new_max must be real numbers")
    if new_min != new_min or new_max != new_max:  # NaN check
        raise ValueError("new_min and new_max must not be NaN")

    # --- Pre-compute the affine transformation parameters ------------------
    scale = (new_max - new_min) / (hi - lo)
    shift = new_min - lo * scale

    def rescale(x: Real) -> Real:
        if not isinstance(x, Real):
            raise TypeError("rescale argument must be a real number")
        if x != x:  # NaN check propagates cleanly
            return x
        return x * scale + shift

    return rescale


__all__ = ["linear_interval_rescaler"]