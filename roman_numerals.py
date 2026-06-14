# roman_numerals.py
"""Roman numeral conversion utilities.

Provides bidirectional conversion between integers and Roman numerals
using the standard subtractive notation (I, V, X, L, C, D, M).

Valid range: 1 <= n <= 3999
"""

from typing import List, Tuple

_VALUES: List[Tuple[int, str]] = [
    (1000, "M"),
    (900, "CM"),
    (500, "D"),
    (400, "CD"),
    (100, "C"),
    (90, "XC"),
    (50, "L"),
    (40, "XL"),
    (10, "X"),
    (9, "IX"),
    (5, "V"),
    (4, "IV"),
    (1, "I"),
]


def to_roman(num: int) -> str:
    """Convert an integer to its Roman numeral representation.

    Args:
        num: An integer in the range [1, 3999].

    Returns:
        The Roman numeral string.

    Raises:
        ValueError: If ``num`` is outside the valid range.
    """
    if not isinstance(num, int) or isinstance(num, bool):
        raise TypeError(f"expected int, got {type(num).__name__}")
    if num < 1 or num > 3999:
        raise ValueError(f"value out of range (1-3999): {num}")

    parts: List[str] = []
    remaining = num
    for value, symbol in _VALUES:
        while remaining >= value:
            parts.append(symbol)
            remaining -= value
    return "".join(parts)


def from_roman(s: str) -> int:
    """Convert a Roman numeral string to an integer.

    Args:
        s: A Roman numeral string (case-insensitive).

    Returns:
        The integer value of the Roman numeral.

    Raises:
        ValueError: If ``s`` is not a valid Roman numeral.
    """
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")
    if not s:
        raise ValueError("empty string is not a valid Roman numeral")

    normalized = s.upper()
    total = 0
    i = 0
    length = len(normalized)
    while i < length:
        # Look for two-character subtractive pairs first.
        if i + 1 < length:
            pair = normalized[i : i + 2]
            if pair in {"IV", "IX", "XL", "XC", "CD", "CM"}:
                total += _VALUES_DICT[pair]
                i += 2
                continue
        ch = normalized[i]
        if ch not in _VALUES_DICT:
            raise ValueError(f"invalid Roman numeral character: {ch!r}")
        total += _VALUES_DICT[ch]
        i += 1
    return total


_VALUES_DICT = {symbol: value for value, symbol in _VALUES}