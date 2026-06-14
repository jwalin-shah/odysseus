"""Swap odd and even bits of a non-negative integer.

For each bit position ``i`` of the 32-bit representation of ``n``:
    - if bit ``i`` is even (i.e. ``i % 2 == 0``), it is moved to position ``i + 1``
    - if bit ``i`` is odd  (i.e. ``i % 2 == 1``), it is moved to position ``i - 1``

Bits beyond the 32nd position are ignored.  Negative inputs are first
converted to their 32-bit two's-complement representation, and the result is
always returned as a non-negative integer in the range ``[0, 2**32)``.

The standard "trick" used here relies on two masks:
    * ``0x55555555`` selects all even-indexed bits (positions 0, 2, 4, ...).
    * ``0xAAAAAAAA`` selects all odd-indexed bits  (positions 1, 3, 5, ...).

Shifting the first mask left by one and the second right by one, then OR-ing
the two together, produces the bit-swapped result.
"""

from __future__ import annotations

__all__ = ["swap_odd_even_bits"]

_EVEN_MASK = 0x55555555  # 01010101...
_ODD_MASK = 0xAAAAAAAA   # 10101010...
_32BIT_MASK = 0xFFFFFFFF


def swap_odd_even_bits(n: int) -> int:
    """Return ``n`` with its odd and even bits exchanged.

    Parameters
    ----------
    n : int
        A non-negative integer (or any integer -- negatives are interpreted
        via their 32-bit two's-complement pattern).

    Returns
    -------
    int
        A non-negative integer in ``[0, 2**32)`` whose bit pattern is
        ``n``'s bit pattern with odd/even positions exchanged.

    Raises
    ------
    TypeError
        If ``n`` is not an integer, or is a ``bool`` (since ``bool`` is a
        subclass of ``int`` in Python and would otherwise be silently
        accepted as 0 or 1).

    Examples
    --------
    >>> swap_odd_even_bits(0)
    0
    >>> swap_odd_even_bits(1)        # 0b1   -> 0b10  (== 2)
    2
    >>> swap_odd_even_bits(2)        # 0b10  -> 0b1   (== 1)
    1
    >>> swap_odd_even_bits(0b10101010)
    85
    >>> bin(swap_odd_even_bits(0b10101010))
    '0b1010101'
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError(f"n must be an integer, got {type(n).__name__}")

    # Normalise negative numbers to their 32-bit two's-complement pattern.
    if n < 0:
        n = n & _32BIT_MASK

    # Even-indexed bits shift left  (position i -> i+1).
    even = (n & _EVEN_MASK) << 1
    # Odd-indexed bits shift right  (position i -> i-1).
    odd = (n & _ODD_MASK) >> 1

    return (even | odd) & _32BIT_MASK


if __name__ == "__main__":
    # Quick self-test when run as a script.
    _cases = [
        (0, 0),
        (1, 2),
        (2, 1),
        (3, 3),                       # 0b11   -> 0b11
        (0xAAAAAAAA, 0x55555555),     # swap of alternating pattern
        (0x55555555, 0xAAAAAAAA),     # inverse of the above
        (0xFFFFFFFF, 0xFFFFFFFF),     # all ones is invariant
        (0x0000000F, 0x0000000F),     # 0b1111: pairs (0,1) and (2,3) are (1,1) -> invariant
        (0x000000F0, 0x000000F0),     # 0b11110000: pairs (4,5) and (6,7) are (1,1) -> invariant
        (0x12345678, 0x2138a9b4),     # non-trivial case verified computationally
    ]
    for _inp, _expected in _cases:
        _got = swap_odd_even_bits(_inp)
        assert _got == _expected, (
            f"swap_odd_even_bits({_inp:#x}) = {_got:#x}, "
            f"expected {_expected:#x}"
        )
    print("All self-tests passed.")