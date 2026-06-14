"""Disarium number validator.

A Disarium number is a number in which the sum of its digits, each raised
to the power of its 1-based position within the number, equals the number
itself.

Examples
--------
    89   -> 8^1 + 9^2            = 8 + 81        = 89
    135  -> 1^1 + 3^2 + 5^3      = 1 + 9 + 125   = 135
    518  -> 5^1 + 1^2 + 8^3      = 5 + 1 + 512   = 518
    598  -> 5^1 + 9^2 + 8^3      = 5 + 81 + 512  = 598
    1306 -> 1^1 + 3^2 + 0^3 + 6^4 = 1 + 9 + 0 + 1296 = 1306
"""

from __future__ import annotations

__all__ = ["is_disarium", "disarium"]


def _check_int(n: object) -> None:
    """Validate that ``n`` is a proper integer argument.

    Booleans are explicitly rejected even though ``bool`` is a subclass of
    ``int`` in Python -- passing ``True``/``False`` to a numeric predicate
    is almost always a programming error and should not be silently
    accepted.
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError(
            f"is_disarium() expected an integer, got {type(n).__name__}"
        )


def is_disarium(n: int) -> bool:
    """Return ``True`` if ``n`` is a Disarium number, otherwise ``False``.

    Parameters
    ----------
    n : int
        A non-negative integer to test. Negative integers always return
        ``False``.

    Returns
    -------
    bool
        ``True`` when the sum of each digit raised to the power of its
        1-based position equals ``n``; ``False`` otherwise.

    Raises
    ------
    TypeError
        If ``n`` is not an integer (or is a ``bool``).
    """
    _check_int(n)

    if n < 0:
        return False

    digits = str(n)
    total = sum(int(digit) ** (index + 1) for index, digit in enumerate(digits))
    return total == n


# Backwards-compatible alias matching the module name.
disarium = is_disarium