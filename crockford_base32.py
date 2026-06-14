"""Crockford Base32 encoding and decoding.

Crockford Base32 uses the alphabet:
    0123456789ABCDEFGHJKMNPQRSTVWXYZ

The letters I, L, O, and U are excluded to avoid visual ambiguity.
I and L both decode to 1, and O decodes to 0. The encoding is
case-insensitive and ignores hyphens and whitespace during decoding.
"""

import re

CROCKFORD_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

# Decoding map including common visual aliases
_DECODE_MAP = {c: i for i, c in enumerate(CROCKFORD_ALPHABET)}
_DECODE_MAP['I'] = 1
_DECODE_MAP['L'] = 1
_DECODE_MAP['O'] = 0


def encode(data: bytes) -> str:
    """Encode ``data`` to a Crockford Base32 string.

    The output is left-padded with zero characters so that the encoded
    length preserves the original byte count for non-zero-leading inputs.
    """
    if not data:
        return ""
    num = int.from_bytes(data, 'big')
    # Number of base32 characters needed to hold the input bits.
    num_chars = (len(data) * 8 + 4) // 5
    if num == 0:
        return CROCKFORD_ALPHABET[0] * num_chars
    digits = []
    temp = num
    while temp > 0:
        digits.append(CROCKFORD_ALPHABET[temp % 32])
        temp //= 32
    # Pad to ``num_chars`` with leading zeros (MSB side).
    while len(digits) < num_chars:
        digits.append(CROCKFORD_ALPHABET[0])
    return ''.join(reversed(digits))


def decode(s: str) -> bytes:
    """Decode a Crockford Base32 string to bytes.

    Hyphens and whitespace are ignored, and decoding is case-insensitive.
    Raises ``ValueError`` on invalid characters.
    """
    if not s:
        return b""
    s = re.sub(r'[-\s]', '', s).upper()
    if not s:
        return b""
    num = 0
    for c in s:
        if c not in _DECODE_MAP:
            raise ValueError(f"Invalid character: {c!r}")
        num = num * 32 + _DECODE_MAP[c]
    # Determine byte length: at least the minimum needed for the value,
    # but also at least the byte count implied by the input length.
    if num == 0:
        min_bytes = 1
    else:
        min_bytes = (num.bit_length() + 7) // 8
    expected_bytes = (len(s) * 5) // 8
    length = max(min_bytes, expected_bytes)
    return num.to_bytes(length, 'big')