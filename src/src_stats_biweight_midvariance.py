import math


def src_stats_biweight_midvariance(x, c=9.0, M=None):
    """Compute the biweight midvariance of a dataset.

    The biweight midvariance is a robust measure of statistical dispersion,
    similar to standard deviation but resistant to outliers. It uses the
    median and median absolute deviation (MAD) for robustness.

    Parameters
    ----------
    x : sequence of numbers
        Input data.
    c : float, optional
        Tuning constant for the bisquare weight function. Default is 9.0.
    M : float, optional
        Pre-computed median of x. If None, the median is computed from x.

    Returns
    -------
    float
        The biweight midvariance. Returns 0.0 for inputs with fewer than
        2 elements or zero MAD.
    """
    n = len(x)
    if n < 2:
        return 0.0

    # Compute median if not provided
    if M is None:
        sorted_x = sorted(x)
        if n % 2 == 1:
            M = float(sorted_x[n // 2])
        else:
            M = (sorted_x[n // 2 - 1] + sorted_x[n // 2]) / 2.0

    # Compute MAD (Median Absolute Deviation)
    abs_dev = sorted(abs(xi - M) for xi in x)
    if n % 2 == 1:
        mad = float(abs_dev[n // 2])
    else:
        mad = (abs_dev[n // 2 - 1] + abs_dev[n // 2]) / 2.0

    if mad == 0:
        return 0.0

    # Compute u values and accumulate A and B
    denom = c * mad
    A = 0.0
    B = 0.0
    count = 0
    for i in range(n):
        u = (x[i] - M) / denom
        if abs(u) < 1.0:
            w = 1.0 - u * u
            A += (x[i] - M) ** 2 * w ** 4
            B += w * (1.0 - 5.0 * u * u)
            count += 1

    if B == 0.0 or count == 0:
        return 0.0

    return math.sqrt(count * A / (B * B))