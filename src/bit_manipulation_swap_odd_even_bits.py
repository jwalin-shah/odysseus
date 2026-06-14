"""Swap odd and even bits in an integer.

Bit at position 0 (even) is swapped with bit at position 1 (odd),
bit at position 2 (even) is swapped with bit at position 3 (odd), and so on.
"""


def bit_manipulation_swap_odd_even_bits(n):
    """Swap the odd and even bits of a non-negative integer.

    Args:
        n: A non-negative integer whose bits are to be swapped.

    Returns:
        A new integer with bits at even positions (0, 2, 4, ...) swapped
        with bits at odd positions (1, 3, 5, ...).

    Raises:
        TypeError: If ``n`` is not an integer.
        ValueError: If ``n`` is negative.
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("n must be an integer")
    if n < 0:
        raise ValueError("n must be non-negative")
    if n == 0:
        return 0

    # Mask for bits at odd positions (1, 3, 5, ...): 0xAA = 0b10101010
    # Mask for bits at even positions (0, 2, 4, ...): 0x55 = 0b01010101
    odd_position_bits = n & 0xAAAAAAAA
    even_position_bits = n & 0x55555555

    # Shift bits at odd positions right (to even positions) and bits at
    # even positions left (to odd positions), then combine.
    return (odd_position_bits >> 1) | (even_position_bits << 1)