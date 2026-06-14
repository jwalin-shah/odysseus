def validators_happy_number(n):
    """Determine whether a number is a happy number.

    A happy number is a number that eventually reaches 1 when it is
    repeatedly replaced by the sum of the squares of its decimal digits.
    Numbers that enter a cycle that does not include 1 are unhappy.

    Parameters
    ----------
    n : int
        The number to check. Non-integer or negative values are
        considered invalid and yield ``False``.

    Returns
    -------
    bool
        ``True`` if ``n`` is a happy number, ``False`` otherwise.
    """
    # Defensive type / value checks. Happy numbers are defined on
    # non-negative integers; anything else is treated as not happy.
    if not isinstance(n, int) or isinstance(n, bool):
        return False
    if n < 0:
        return False

    # Track every value we have already seen. Any repeat means we
    # are stuck in a cycle and the number can never reach 1.
    seen = set()
    while n != 1 and n not in seen:
        seen.add(n)
        # Sum of squares of decimal digits.
        n = sum(int(digit) ** 2 for digit in str(n))

    return n == 1