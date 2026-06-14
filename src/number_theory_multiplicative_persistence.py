"""Multiplicative persistence of a non-negative integer.

The multiplicative persistence of a non-negative integer n is the number
of times you must multiply the digits of n until a single digit is
reached.

Examples
--------
>>> number_theory_multiplicative_persistence(39)
3
>>> number_theory_multiplicative_persistence(999)
4
>>> number_theory_multiplicative_persistence(0)
0
"""


def _multiply_digits(value: int) -> int:
    """Return the product of the decimal digits of ``value``."""
    product = 1
    for ch in str(value):
        product *= int(ch)
    return product


def number_theory_multiplicative_persistence(n: int) -> int:
    """Return the multiplicative persistence of the non-negative integer ``n``.

    Parameters
    ----------
    n : int
        A non-negative integer whose persistence should be computed.

    Returns
    -------
    int
        The number of multiplicative steps required to reduce ``n`` to
        a single digit.  Any value already smaller than ``10`` (including
        ``0``) has persistence ``0``.

    Raises
    ------
    TypeError
        If ``n`` is not an integer.
    ValueError
        If ``n`` is negative.
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("n must be an integer")
    if n < 0:
        raise ValueError("n must be a non-negative integer")

    # Single digit numbers (including 0) need zero steps.
    if n < 10:
        return 0

    steps = 0
    current = n
    while current >= 10:
        current = _multiply_digits(current)
        steps += 1
    return steps


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    samples = [0, 5, 10, 25, 39, 77, 679, 6788, 68889, 999]
    for s in samples:
        print(f"{s}: {number_theory_multiplicative_persistence(s)}")