"""
Recursive Josephus Survivor Locator

This module provides a recursive solution to the classic Josephus problem.

In the Josephus problem, ``n`` people stand in a circle. Starting from
position 1, every ``k``-th person is eliminated. The process continues
around the circle until only one person remains. This module computes
the 1-indexed position of that survivor using a direct recursive
formulation derived from the standard recurrence:

    J(n, k) = 1                                 when n == 1
    J(n, k) = (J(n - 1, k) + k - 1) % n + 1     otherwise
"""


def recursive_josephus_survivor_locator(n, k):
    """
    Recursively compute the position of the survivor in the Josephus problem.

    Parameters
    ----------
    n : int
        Number of people standing in the circle. Must be a non-negative
        integer. ``n == 0`` is treated as a degenerate edge case.
    k : int
        Step size: every ``k``-th person is eliminated. Must be a
        positive integer; non-positive values are treated as invalid.

    Returns
    -------
    int
        The 1-indexed position of the survivor, or ``0`` if the
        supplied arguments are not valid for the problem
        (non-integers, ``n <= 0``, or ``k <= 0``).
    """
    # --- input validation ------------------------------------------------
    # Only accept plain integers; anything else is considered invalid
    # for the classical Josephus problem.
    if not isinstance(n, int) or not isinstance(k, int):
        return 0
    if isinstance(n, bool) or isinstance(k, bool):
        # ``bool`` is a subclass of ``int`` in Python; reject it so that
        # ``True``/``False`` aren't silently coerced into ``1``/``0``.
        return 0

    # Negative or zero values are not meaningful for this problem.
    if n <= 0 or k <= 0:
        return 0

    # --- base case -------------------------------------------------------
    # With a single person in the circle, that person is the survivor.
    if n == 1:
        return 1

    # --- recursive case --------------------------------------------------
    # J(n, k) = (J(n - 1, k) + k - 1) % n + 1
    return (recursive_josephus_survivor_locator(n - 1, k) + k - 1) % n + 1