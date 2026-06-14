def stats_gini(values):
    """Calculate the Gini coefficient for a list of non-negative numeric values.

    The Gini coefficient is a measure of statistical dispersion, ranging from 0
    (perfect equality — all values are the same) and approaching 1 (perfect
    inequality — one value holds everything).

    Formula (for sorted, non-negative values x_(1) <= x_(2) <= ... <= x_(n))::

        G = (2 * sum_{i=1..n} i * x_(i)) / (n * sum(x)) - (n + 1) / n

    Edge cases:
        * Empty input  -> 0.0
        * Single value -> 0.0
        * All equal (including all zeros) -> 0.0

    Parameters
    ----------
    values : sequence of numbers
        Non-negative numeric values. Order does not matter (the function
        sorts internally). A copy is sorted; the input is not mutated.

    Returns
    -------
    float
        The Gini coefficient in [0, 1).
    """
    n = len(values)
    if n < 2:
        return 0.0

    sorted_values = sorted(values)
    total = sum(sorted_values)
    if total == 0:
        return 0.0

    # Weighted sum of sorted values: 1*x1 + 2*x2 + ... + n*xn
    weighted_sum = 0.0
    for i, x in enumerate(sorted_values, start=1):
        weighted_sum += i * x

    gini = (2.0 * weighted_sum) / (n * total) - (n + 1.0) / n
    return gini