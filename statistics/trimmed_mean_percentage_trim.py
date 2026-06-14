def trimmed_mean_percentage_trim(data, percentage):
    """
    Calculate the trimmed mean of a dataset by removing a specified percentage
    of values from both the low and high ends of the sorted data, then averaging
    what remains.

    Parameters
    ----------
    data : iterable of numbers
        The dataset to compute the trimmed mean over.
    percentage : float or int
        The percentage of data to trim from EACH end of the sorted dataset.
        Must satisfy 0 <= percentage < 50. The number of elements trimmed from
        each side is computed as int(len(data) * percentage / 100).

    Returns
    -------
    float
        The trimmed mean of the data.

    Raises
    ------
    ValueError
        If data is empty, if percentage is not in [0, 50), or if trimming would
        remove all data points.
    """
    # Normalise to a list so we can inspect length and sort.
    data = list(data)

    if not data:
        raise ValueError("data must not be empty")

    if percentage < 0 or percentage >= 50:
        raise ValueError("percentage must be in the range [0, 50)")

    sorted_data = sorted(data)
    n = len(sorted_data)

    # Number of values to drop from each end.
    k = int(n * percentage / 100)

    trimmed = sorted_data[k:n - k] if k > 0 else sorted_data

    if not trimmed:
        raise ValueError("trimmed data is empty; reduce the trim percentage")

    return sum(trimmed) / len(trimmed)


if __name__ == "__main__":
    # Simple sanity demo.
    sample = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    print("10% trim  :", trimmed_mean_percentage_trim(sample, 10))
    print("0% trim   :", trimmed_mean_percentage_trim(sample, 0))
    print("20% trim  :", trimmed_mean_percentage_trim(sample, 20))