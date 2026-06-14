"""Winsorized mean implementation."""


def winsorized_mean(data, proportion=0.05):
    """
    Compute the winsorized mean of a dataset.

    The winsorized mean replaces the top and bottom proportion of values
    with the next available value, then computes the mean. This is less
    sensitive to outliers than the arithmetic mean.

    Parameters
    ----------
    data : sequence
        Input data (must be non-empty).
    proportion : float, optional
        Proportion of values to winsorize from each end. Must be in [0, 1].
        Values above 0.5 are clamped to 0.5, since winsorizing more than
        50% from each tail is not meaningful. Default is 0.05.

    Returns
    -------
    float
        The winsorized mean.

    Raises
    ------
    ValueError
        If data is empty or proportion is outside [0, 1].
    """
    if not data:
        raise ValueError("data must not be empty")

    proportion = float(proportion)
    if proportion < 0 or proportion > 1:
        raise ValueError("proportion must be between 0 and 1")

    # Winsorizing more than 50% from each tail is not meaningful; clamp.
    proportion = min(proportion, 0.5)

    sorted_data = sorted(data)
    n = len(sorted_data)
    k = int(proportion * n)

    if k == 0:
        return sum(sorted_data) / n

    # The value used to replace the bottom k values (the (k+1)th smallest).
    lower_replacement = sorted_data[k]
    # The value used to replace the top k values (the (k+1)th largest).
    upper_replacement = sorted_data[n - k - 1]

    winsorized = list(sorted_data)
    for i in range(k):
        winsorized[i] = lower_replacement
        winsorized[n - 1 - i] = upper_replacement

    return sum(winsorized) / n