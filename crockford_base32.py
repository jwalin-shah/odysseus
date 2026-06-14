"""Crockford Base32 encoding/decoding.

Alphabet: 0123456789ABCDEFGHJKMNPQRSTVWXYZ (32 symbols, excludes I, L, O, U).
Decode is case-insensitive and maps aliases: O/o→0, I/i/L/l→1.
"""

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ENCODE_TABLE = {i: c for i, c in enumerate(_ALPHABET)}
_DECODE_TABLE = {c: i for i, c in enumerate(_ALPHABET)}
_DECODE_TABLE.update({"O": 0, "I": 1, "L": 1})


def encode(n: int) -> str:
    """Encode a non-negative integer to Crockford Base32."""
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError(f"expected int, got {type(n).__name__}")
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return "0"
    chars = []
    while n:
        chars.append(_ENCODE_TABLE[n % 32])
        n //= 32
    return "".join(reversed(chars))


def decode(s: str) -> int:
    """Decode a Crockford Base32 string to a non-negative integer."""
    if not isinstance(s, str):
        raise TypeError(f"expected str, got {type(s).__name__}")
    if not s:
        raise ValueError("empty string")
    result = 0
    for ch in s.upper():
        if ch not in _DECODE_TABLE:
            raise ValueError(f"invalid character: {ch!r}")
        result = result * 32 + _DECODE_TABLE[ch]
    return result
