"""
Multiplicative persistence of a non-negative integer.

The multiplicative persistence of a non-negative integer ``n`` is the number
of times you must multiply the digits of ``n`` (in base 10) together until
you reach a single digit.
"""


def multiplicative_persistence(n):
    """
    Calculate the multiplicative persistence of a non-negative integer.

    The multiplicative persistence is the number of times you must multiply
    the digits of the number together (replacing the number with the result)
    until you reach a single digit.

    Parameters
    ----------
    n : int
        A non-negative integer.

    Returns
    -------
    int
        The multiplicative persistence of ``n``.

    Raises
    ------
    TypeError
        If ``n`` is not an integer.
    ValueError
        If ``n`` is negative.

    Examples
    --------
    >>> multiplicative_persistence(39)
    3
    >>> multiplicative_persistence(999)
    4
    >>> multiplicative_persistence(4)
    0
    >>> multiplicative_persistence(10)
    1
    """
    # Reject booleans explicitly, even though ``bool`` is a subclass of ``int``,
    # because they are not conceptually integers for this function.
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("multiplicative_persistence requires an integer")
    if n < 0:
        raise ValueError("multiplicative_persistence requires a non-negative integer")

    count = 0
    while n >= 10:
        product = 1
        for digit in str(n):
            product *= int(digit)
        n = product
        count += 1
    return count