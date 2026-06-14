def bit_ops_reverse(n, bit_width=None):
    """Reverse the bits of a non-negative integer.

    If ``bit_width`` is ``None``, the reversal is performed within the
    minimum number of bits required to represent ``n`` (i.e.
    ``n.bit_length()`` bits, or 1 bit when ``n`` is zero).

    If ``bit_width`` is provided, the reversal is performed within that
    many bits, zero-padding ``n`` on the left as needed.

    Parameters
    ----------
    n : int
        A non-negative integer whose bits are to be reversed.
    bit_width : int, optional
        Fixed bit width for the reversal. Must be positive when given.

    Returns
    -------
    int
        The bit-reversed value.

    Examples
    --------
    >>> bit_ops_reverse(0)
    0
    >>> bit_ops_reverse(1)
    1
    >>> bit_ops_reverse(2)        # 10 -> 01
    1
    >>> bit_ops_reverse(12)       # 1100 -> 0011
    3
    >>> bit_ops_reverse(12, 8)    # 00001100 -> 00110000
    48
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("n must be an int")
    if n < 0:
        raise ValueError("n must be non-negative")

    if bit_width is None:
        bit_width = max(n.bit_length(), 1)
    else:
        if not isinstance(bit_width, int) or isinstance(bit_width, bool):
            raise TypeError("bit_width must be an int")
        if bit_width < 1:
            raise ValueError("bit_width must be at least 1")

    result = 0
    for i in range(bit_width):
        if (n >> i) & 1:
            result |= 1 << (bit_width - 1 - i)
    return result


def popcount(n):
    """Return the number of 1-bits in the binary representation of ``n``."""
    return bin(n).count("1")