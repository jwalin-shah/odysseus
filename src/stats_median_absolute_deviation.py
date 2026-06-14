def stats_median_absolute_deviation(data):
    """
    Compute the Median Absolute Deviation (MAD) of a numeric sequence.

    MAD = median(|x_i - median(x)|)

    Parameters
    ----------
    data : sequence of numbers (list, tuple, etc.)

    Returns
    -------
    float
        The median absolute deviation. Returns 0.0 for empty input or
        a single-element input.
    """
    # Convert to a list of numbers; handle empty input
    try:
        values = [float(x) for x in data]
    except TypeError:
        # data is not iterable
        raise TypeError("data must be an iterable of numeric values")
    except ValueError:
        raise ValueError("data must contain only numeric values")

    n = len(values)
    if n == 0:
        return 0.0

    sorted_values = sorted(values)
    mid = n // 2
    if n % 2 == 0:
        median = (sorted_values[mid - 1] + sorted_values[mid]) / 2.0
    else:
        median = sorted_values[mid]

    deviations = [abs(v - median) for v in sorted_values]
    deviations_sorted = sorted(deviations)
    mid_d = len(deviations_sorted) // 2
    if len(deviations_sorted) % 2 == 0:
        mad = (deviations_sorted[mid_d - 1] + deviations_sorted[mid_d]) / 2.0
    else:
        mad = deviations_sorted[mid_d]

    return float(mad)