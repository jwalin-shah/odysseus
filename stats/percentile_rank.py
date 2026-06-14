def percentile_rank(data, x):
    """Calculate the percentile rank of a value in a dataset.

    The percentile rank is defined as the percentage of values in the
    dataset that are less than or equal to the given value. This is the
    "weak" / inclusive form of percentile rank (sometimes called the
    empirical CDF evaluated at x).

    For example, in the dataset [1, 2, 3, 4, 5]:
        - percentile_rank(..., 1) == 20.0  (1 of 5 values <= 1)
        - percentile_rank(..., 4) == 80.0  (4 of 5 values <= 4)
        - percentile_rank(..., 5) == 100.0 (5 of 5 values <= 5)

    Args:
        data: An iterable of numeric values (list, tuple, range, generator,
            etc.). The data does not need to be sorted.
        x: The numeric value whose percentile rank should be computed.

    Returns:
        float: The percentile rank of ``x`` in ``data``, expressed as a
        percentage in the range [0.0, 100.0].

    Raises:
        ValueError: If ``data`` is None or empty.
    """
    if data is None:
        raise ValueError("data cannot be None")

    # Materialize the iterable (works for lists, tuples, ranges, generators,
    # and any other iterable) so we can safely take its length and iterate.
    data = list(data)
    n = len(data)

    if n == 0:
        raise ValueError("data cannot be empty")

    # Count how many elements are less than or equal to x.
    count = sum(1 for value in data if value <= x)

    return (count / n) * 100.0