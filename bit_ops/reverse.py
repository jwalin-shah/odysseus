def reverse(n):
    """Reverse the binary representation of a non-negative integer.

    The binary representation of n (without leading zeros) is reversed.
    For example: reverse(0b1101) == 0b1011  (i.e., 13 -> 11)

    Args:
        n: A non-negative integer.

    Returns:
        The integer whose binary representation is the bit-reversal of n.

    Raises:
        TypeError: If n is not an integer (or is a bool).
        ValueError: If n is negative.
    """
    if isinstance(n, bool) or not isinstance(n, int):
        raise TypeError("reverse() requires an integer")
    if n < 0:
        raise ValueError("reverse() requires a non-negative integer")

    result = 0
    while n > 0:
        result = (result << 1) | (n & 1)
        n >>= 1
    return result