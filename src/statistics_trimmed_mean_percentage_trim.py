from typing import Iterable, Union, List


def statistics_trimmed_mean_percentage_trim(
    data: Iterable[Union[int, float]],
    percentage: float = 0.1
) -> float:
    """
    Calculate the trimmed (truncated) mean of a dataset by removing a specified
    proportion of values from each end (the smallest and largest values) before
    computing the arithmetic mean.

    This statistic is useful for estimating a population mean from a sample
    that may contain outliers, because extreme values have a disproportionate
    influence on the ordinary mean.

    Args:
        data: An iterable of numeric values (int or float). Strings, ``None``,
            and other non-numeric types are not permitted and will raise
            ``TypeError``.
        percentage: A float in the range [0, 0.5) representing the proportion
            of data to remove from each end. For example, ``0.1`` means 10%
            will be removed from the bottom and 10% from the top. The default
            is ``0.1``.

    Returns:
        The trimmed mean as a ``float``.

    Raises:
        TypeError: If ``percentage`` is not a number, or if any value in
            ``data`` is not numeric.
        ValueError: If ``data`` is empty, or if ``percentage`` is not in
            the interval [0, 0.5).

    Examples:
        >>> statistics_trimmed_mean_percentage_trim([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 0.1)
        5.5
        >>> statistics_trimmed_mean_percentage_trim([1, 2, 3, 4, 5], 0)
        3.0
        >>> statistics_trimmed_mean_percentage_trim([1, 2, 3, 4, 5], 0.4)
        3.0
    """
    # --- Validate the `percentage` argument ---------------------------------
    # Reject booleans explicitly because in Python ``bool`` is a subclass of
    # ``int`` and would otherwise pass the ``isinstance`` check below.
    if isinstance(percentage, bool) or not isinstance(percentage, (int, float)):
        raise TypeError("percentage must be a number (int or float)")

    if percentage < 0 or percentage >= 0.5:
        raise ValueError(
            "percentage must be between 0 and 0.5 (exclusive of 0.5); "
            f"got {percentage!r}"
        )

    # --- Convert `data` to a list of floats --------------------------------
    # We deliberately do *not* use a list comprehension with ``float()`` so we
    # can re-raise ``ValueError`` (raised by ``float('abc')``) as a
    # ``TypeError`` for a uniform error type when the data is malformed.
    data_list: List[float] = []
    for item in data:
        try:
            data_list.append(float(item))
        except (ValueError, TypeError):
            raise TypeError(
                "All values in data must be numeric; "
                f"got {type(item).__name__}: {item!r}"
            )

    if not data_list:
        raise ValueError("data cannot be empty")

    # --- Sort and trim -----------------------------------------------------
    sorted_data = sorted(data_list)
    n = len(sorted_data)

    # Number of observations to discard from each tail.
    # Using ``int`` truncates toward zero, matching the behaviour of
    # ``scipy.stats.trim_mean``.
    k = int(n * percentage)

    # Since ``percentage < 0.5``, ``int(n * percentage) < n / 2`` is guaranteed
    # for any ``n >= 1``, so ``n - k > k`` and the slice below is always valid.
    trimmed = sorted_data[k:n - k]
    return sum(trimmed) / len(trimmed)