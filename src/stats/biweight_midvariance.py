"""Biweight midvariance: a robust measure of statistical dispersion.

The biweight midvariance is a robust estimator of scale (analogous to
the variance) introduced by Tukey.  Observations far from the location
estimate are down-weighted via a bisquare weight function defined in
units of the median absolute deviation (MAD), making the estimator
resistant to extreme outliers.
"""
from typing import Iterable, Optional


def _median(sorted_data):
    """Return the median of a pre-sorted numeric sequence."""
    n = len(sorted_data)
    if n == 0:
        raise ValueError("Cannot compute median of empty data.")
    if n % 2 == 1:
        return float(sorted_data[n // 2])
    return 0.5 * (sorted_data[n // 2 - 1] + sorted_data[n // 2])


def biweight_midvariance(
    data: Iterable[float],
    c: float = 9.0,
    M: Optional[float] = None,
) -> float:
    """Compute the biweight midvariance of a 1-D data set.

    Parameters
    ----------
    data : array-like
        1-D iterable of numeric data.
    c : float, optional
        Strictly positive tuning constant controlling the point at
        which an observation receives zero weight.  Observations whose
        distance from the location estimate exceeds ``c * MAD`` are
        excluded from the computation.  Default is 9.0.
    M : float, optional
        Pre-computed location estimate.  If ``None`` (default), the
        sample median of ``data`` is used.

    Returns
    -------
    float
        The biweight midvariance.  Trivial inputs (a single observation
        or all-equal values) yield ``0.0``.

    Raises
    ------
    ValueError
        If ``data`` is empty or ``c`` is not strictly positive.
    """
    if c <= 0:
        raise ValueError("Tuning constant c must be positive.")

    # Materialise and sort the input once - both the median and the
    # median absolute deviation can be obtained in linear time.
    sorted_data = sorted(float(x) for x in data)
    n = len(sorted_data)

    if n == 0:
        raise ValueError("data must contain at least one element.")
    if n == 1:
        return 0.0

    # Location estimate (median) - either supplied or computed.
    if M is None:
        M = _median(sorted_data)

    # Median absolute deviation.
    abs_devs = sorted(abs(x - M) for x in sorted_data)
    mad = _median(abs_devs)

    if mad == 0.0:
        # All points coincide with the median, so dispersion is zero.
        return 0.0

    scale = c * mad
    w_sum = 0.0
    w_sq_sum = 0.0
    num = 0.0

    for x in sorted_data:
        u = (x - M) / scale
        # Observations with |u| >= 1 receive zero weight by design.
        if -1.0 < u < 1.0:
            one_minus_u2 = 1.0 - u * u
            w = one_minus_u2 * one_minus_u2
            d = x - M
            w_sum += w
            w_sq_sum += w * w
            num += w * d * d

    denom = w_sum * w_sum - w_sq_sum
    if denom == 0.0:
        return 0.0

    return n * num / denom