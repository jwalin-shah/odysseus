"""Happy number validator.

A *happy number* is a positive integer that, when repeatedly replaced by
the sum of the squares of its decimal digits, eventually reaches 1.
Numbers whose sequence never reaches 1 fall into a cycle and are
*unhappy*.

Examples
--------
>>> is_happy(1)
True
>>> is_happy(7)
True
>>> is_happy(19)
True
>>> is_happy(2)
False
>>> is_happy(0)
False
"""

from __future__ import annotations

from typing import Union


def _sum_of_squares_of_digits(n: int) -> int:
    """Return the sum of the squares of the decimal digits of ``n``."""
    total = 0
    while n > 0:
        digit = n % 10
        total += digit * digit
        n //= 10
    return total


def is_happy(n: int) -> bool:
    """Return ``True`` if ``n`` is a happy number, ``False`` otherwise.

    Parameters
    ----------
    n:
        A non-negative integer to test. Booleans are rejected because
        ``bool`` is a subclass of ``int`` in Python but conceptually
        should not be considered here.

    Returns
    -------
    bool
        ``True`` when the iterative "sum of squares of digits" process
        eventually reaches 1; ``False`` when it falls into a cycle that
        does not contain 1.

    Raises
    ------
    TypeError
        If ``n`` is not a plain integer.
    ValueError
        If ``n`` is negative.
    """
    # ``bool`` is technically a subclass of ``int`` in Python, but it does
    # not make semantic sense here, so we explicitly reject it.
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError(
            "n must be an integer, got {!r}".format(type(n).__name__)
        )
    if n < 0:
        raise ValueError(
            "n must be a non-negative integer, got {}".format(n)
        )

    # 0 -> 0 -> 0 -> ... so it never reaches 1 and is unhappy.
    if n == 0:
        return False

    seen: set[int] = set()
    while n != 1 and n not in seen:
        seen.add(n)
        n = _sum_of_squares_of_digits(n)
    return n == 1


# Convenience alias matching the module name.
happy_number = is_happy

__all__ = ["is_happy", "happy_number"]


if __name__ == "__main__":  # pragma: no cover - manual smoke check
    import sys

    for arg in sys.argv[1:]:
        try:
            value = int(arg)
        except ValueError:
            print("{!r} is not a valid integer".format(arg))
            continue
        print("{} -> {}".format(value, "happy" if is_happy(value) else "unhappy"))