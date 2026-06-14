"""Tap code encoder/decoder.

Tap code is a cipher where each letter is represented by two groups of taps:
the number of taps in the first group indicates the row, and the number of
taps in the second group indicates the column of a grid containing the letters.

This implementation uses a 5-row grid to accommodate all 26 letters
without combining C and K (so that encoding and decoding round-trips
perfectly for every letter of the alphabet):

    Row 1: A B C D E
    Row 2: F G H I J
    Row 3: K L M N O
    Row 4: P Q R S T
    Row 5: U V W X Y Z

The encoded form is a string of space-separated "row.col" pairs, where
row and col are 1-based indices into the grid.
"""


def _char_to_position(char):
    """Return (row, col) for an alphabetic character A-Z (case-insensitive)."""
    upper = char.upper()
    if not ('A' <= upper <= 'Z'):
        raise ValueError(f"Invalid character: {char!r}")
    idx = ord(upper) - ord('A')
    if idx < 20:  # A-T
        return (idx // 5 + 1, idx % 5 + 1)
    else:  # U-Z, all in the final row
        return (5, idx - 19)


def _position_to_char(row, col):
    """Return the character A-Z for the given (row, col) grid position."""
    if not (1 <= row <= 5):
        raise ValueError(f"Row out of range: {row}")
    if row < 5:
        if not (1 <= col <= 5):
            raise ValueError(f"Column out of range: {col}")
        idx = (row - 1) * 5 + (col - 1)
    else:  # last row has 6 columns to fit U-Z
        if not (1 <= col <= 6):
            raise ValueError(f"Column out of range: {col}")
        idx = 20 + (col - 1)
    return chr(ord('A') + idx)


def encode(text):
    """Encode text into a tap code string.

    Each letter is converted to a "row.col" pair, and consecutive
    letters are joined with a single space. Non-alphabetic characters
    raise ValueError.
    """
    if not text:
        return ""
    parts = []
    for char in text:
        row, col = _char_to_position(char)
        parts.append(f"{row}.{col}")
    return " ".join(parts)


def decode(code):
    """Decode a tap code string back into text.

    Expects a string of space-separated "row.col" pairs as produced
    by encode(). Raises ValueError for malformed input (wrong number
    of dot-separated parts, non-numeric values, or out-of-range
    row/column indices).
    """
    if not code:
        return ""
    result = []
    for group in code.split(" "):
        if "." not in group:
            raise ValueError(f"Invalid group shape: {group!r}")
        parts = group.split(".")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid group shape: {group!r}")
        try:
            row = int(parts[0])
            col = int(parts[1])
        except ValueError:
            raise ValueError(f"Invalid group shape: {group!r}")
        result.append(_position_to_char(row, col))
    return "".join(result)