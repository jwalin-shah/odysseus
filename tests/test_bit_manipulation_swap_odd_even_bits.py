"""Tests for bit_manipulation_swap_odd_even_bits."""
import os
import sys

import pytest

# Ensure the src directory is on the path so we can import the implementation.
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

from bit_manipulation_swap_odd_even_bits import (  # noqa: E402
    bit_manipulation_swap_odd_even_bits,
)


class TestSwapOddEvenBits:
    """Tests for the bit_manipulation_swap_odd_even_bits function."""

    def test_zero(self):
        assert bit_manipulation_swap_odd_even_bits(0) == 0

    def test_one_swaps_to_two(self):
        # 1 = 0b01 -> swap -> 0b10 = 2
        assert bit_manipulation_swap_odd_even_bits(1) == 2

    def test_two_swaps_to_one(self):
        # 2 = 0b10 -> swap -> 0b01 = 1
        assert bit_manipulation_swap_odd_even_bits(2) == 1

    def test_three_is_invariant(self):
        # 3 = 0b11 -> swap -> 0b11 = 3 (symmetric)
        assert bit_manipulation_swap_odd_even_bits(3) == 3

    def test_twelve_is_invariant(self):
        # 12 = 0b1100 -> swap -> 0b1100 = 12 (pattern 10 10 is symmetric)
        assert bit_manipulation_swap_odd_even_bits(12) == 12

    def test_known_lookup_table(self):
        # Verified against the standard swap-odd-even-bits algorithm.
        cases = [
            (0, 0),
            (1, 2),
            (2, 1),
            (3, 3),
            (4, 8),
            (5, 10),
            (6, 9),
            (7, 11),
            (8, 4),
            (9, 6),
            (10, 5),
            (11, 7),
            (12, 12),
            (13, 14),
            (14, 13),
            (15, 15),
        ]
        for n, want in cases:
            assert bit_manipulation_swap_odd_even_bits(n) == want, (
                f"swap_odd_even_bits({n}) expected {want}"
            )

    def test_large_value_alternating_pattern(self):
        # 0xAAAAAAAA has bits set at all odd positions; after swap they
        # should all be at even positions -> 0x55555555, and vice versa.
        assert bit_manipulation_swap_odd_even_bits(0xAAAAAAAA) == 0x55555555
        assert bit_manipulation_swap_odd_even_bits(0x55555555) == 0xAAAAAAAA

    def test_double_swap_returns_original(self):
        # Swapping twice must return the original value (involution).
        for n in [0, 1, 2, 3, 5, 10, 15, 255, 0x12345678, 0xDEADBEEF]:
            once = bit_manipulation_swap_odd_even_bits(n)
            twice = bit_manipulation_swap_odd_even_bits(once)
            assert twice == n, f"double swap of {n} gave {twice}"

    def test_negative_raises_value_error(self):
        with pytest.raises(ValueError):
            bit_manipulation_swap_odd_even_bits(-1)

    def test_non_integer_raises_type_error(self):
        with pytest.raises(TypeError):
            bit_manipulation_swap_odd_even_bits(1.5)
        with pytest.raises(TypeError):
            bit_manipulation_swap_odd_even_bits("10")