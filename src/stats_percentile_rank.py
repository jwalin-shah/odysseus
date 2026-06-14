def percentile_rank(data, x):
    """
    Calculate the percentile rank of x in the given data.

    The percentile rank is the percentage of values in the data that fall
    at or below x, using the standard formula (L + 0.5*S) / N * 100, where:
    - L = number of values strictly less than x
    - S = number of values equal to x
    - N = total number of values in the dataset

    This formulation naturally keeps the result bounded within [0, 100]:
    - A value below all data points yields 0.0
    - A value above all data points yields 100.0
    - Values inside the range yield an interpolated rank

    Parameters
    ----------
    data : iterable of numbers
        A non-empty collection of numeric values.
    x : float or int
        The value whose percentile rank is to be computed.

    Returns
    -------
    float
        The percentile rank of x, always in the closed interval [0.0, 100.0].

    Raises
    ------
    ValueError
        If ``data`` is empty or ``None``.
    """
    if data is None:
        raise ValueError("data must not be None")

    data_list = list(data)
    n = len(data_list)

    if n == 0:
        raise ValueError("data must not be empty")

    count_below = 0
    count_equal = 0
    for v in data_list:
        if v < x:
            count_below += 1
        elif v == x:
            count_equal += 1

    # Standard "exclusive" / linear-interpolation percentile rank formula.
    # This is bounded in [0, 100] for any real x:
    #   - when x is below the minimum: L=0, S=0 -> PR = 0
    #   - when x is above the maximum: L=N, S=0 -> PR = 100
    pr = (count_below + 0.5 * count_equal) * 100.0 / n

    # Defensive clamp; the formula above is already in [0, 100], but we
    # guard against any floating-point edge cases.
    if pr < 0.0:
        pr = 0.0
    elif pr > 100.0:
        pr = 100.0

    return float(pr)