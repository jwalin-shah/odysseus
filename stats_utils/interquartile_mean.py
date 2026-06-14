def interquartile_mean(data):
    """
    Calculate the interquartile mean of a dataset.

    The interquartile mean (IQM) is a measure of central tendency computed
    by discarding the lower and upper 25% of the sorted data and taking
    the arithmetic mean of the remaining (middle 50%) values.

    Args:
        data: An iterable of numeric values (ints or floats).

    Returns:
        The interquartile mean as a float.

    Raises:
        ValueError: If ``data`` is empty.
    """
    if not data:
        raise ValueError("Data cannot be empty")

    sorted_data = sorted(data)
    n = len(sorted_data)

    if n == 1:
        return float(sorted_data[0])

    # Number of values to trim from each end (floor of 25% of n).
    k = n // 4

    # Keep the middle portion: drop ``k`` smallest and ``k`` largest.
    # When ``k`` is 0 we keep every value, which is the natural behaviour
    # for very small datasets (e.g. n in {2, 3}).
    if k == 0:
        filtered = sorted_data
    else:
        filtered = sorted_data[k:n - k]
        # Guard against an empty middle slice (shouldn't happen for n >= 4
        # since 2*k <= n/2 < n, but be defensive).
        if not filtered:
            filtered = sorted_data

    return sum(filtered) / len(filtered)