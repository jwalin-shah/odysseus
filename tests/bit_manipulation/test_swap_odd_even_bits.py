"""Tests for :func:`bit_manipulation.swap_odd_even_bits.swap_odd_even_bits`."""

import os
import sys

import pytest

# Allow running the tests directly from this directory without installing
# the package.  We add the repository root (one directory up from
# "tests/bit_manipulation/") to sys.path.
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from bit_manipulation.swap_odd_even_bits import swap_odd_even_bits


# ---------------------------------------------------------------------------
# Basic single-bit and small-value cases
# ---------------------------------------------------------------------------


def test_zero_remains_zero():
    """Swapping bits of zero must still be zero."""
    assert swap_odd_even_bits(0) == 0


def test_single_low_bit_moves_up():
    """``0b1`` (bit 0 set) becomes ``0b10`` (bit 1 set)."""
    assert swap_odd_even_bits(1) == 2


def test_single_bit_one_moves_down():
    """``0b10`` (bit 1 set) becomes ``0b1`` (bit 0 set)."""
    assert swap_odd_even_bits(2) == 1


def test_two_bits_invariant():
    """``0b11`` swaps to itself because each bit just moves to the other slot."""
    assert swap_odd_even_bits(3) == 3


def test_low_nibble_swap():
    """The low nibble ``0b1111`` swaps to itself (all pairs are 1,1)."""
    assert swap_odd_even_bits(0x0F) == 0x0F


def test_high_nibble_swap():
    """``0b11110000`` (0xF0) swaps to itself (pairs (4,5) and (6,7) are both 1,1)."""
    assert swap_odd_even_bits(0xF0) == 0xF0


# ---------------------------------------------------------------------------
# Alternating / all-ones / all-zeros patterns
# ---------------------------------------------------------------------------


def test_alternating_bits_swap():
    """``0b10101010`` swaps to ``0b01010101``."""
    assert swap_odd_even_bits(0b10101010) == 0b01010101
    # The operation is its own inverse.
    assert swap_odd_even_bits(0b01010101) == 0b10101010


def test_full_alternating_masks_swap():
    """The two canonical masks must swap with each other."""
    assert swap_odd_even_bits(0xAAAAAAAA) == 0x55555555
    assert swap_odd_even_bits(0x55555555) == 0xAAAAAAAA


def test_all_ones_unchanged():
    """All ones is a fixed point: every bit just moves to an adjacent slot."""
    assert swap_odd_even_bits(0xFFFFFFFF) == 0xFFFFFFFF


def test_result_fits_in_32_bits():
    """The returned value must always fit in a 32-bit unsigned word."""
    for value in (0, 1, 2, 3, 0xDEADBEEF, 0xFFFFFFFF):
        result = swap_odd_even_bits(value)
        assert 0 <= result < 2**32
        assert isinstance(result, int)


# ---------------------------------------------------------------------------
# Involution property: applying the swap twice returns the original value.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    [0, 1, 2, 3, 5, 7, 42, 0x123, 0xDEADBEEF, 0xFFFFFFFF, 0xAAAAAAAA],
)
def test_involution(value):
    """Swapping twice must always yield the original value (within 32 bits)."""
    original = value & 0xFFFFFFFF
    assert swap_odd_even_bits(swap_odd_even_bits(value)) == original


# ---------------------------------------------------------------------------
# Negative inputs and 32-bit truncation
# ---------------------------------------------------------------------------


def test_negative_one_is_all_ones():
    """``-1`` interpreted in two's-complement 32-bit form is ``0xFFFFFFFF``."""
    assert swap_odd_even_bits(-1) == 0xFFFFFFFF


def test_negative_value_uses_low_32_bits():
    """Only the low 32 bits of a negative number participate in the swap."""
    # -2 in 32-bit two's complement = 0xFFFFFFFE = bit0=0, bits1-31=1.
    # pair (0,1): (0,1) -> (1,0); all other pairs are (1,1) -> (1,1).
    # Result: bit0=1, bit1=0, bits2-31=1 = 0xFFFFFFFD.
    assert swap_odd_even_bits(-2) == 0xFFFFFFFD


# ---------------------------------------------------------------------------
# Type / argument validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", [1.0, "5", None, [1], (1,), {1: 2}])
def test_non_integer_raises_type_error(bad):
    """Non-integer arguments must be rejected with ``TypeError``."""
    with pytest.raises(TypeError):
        swap_odd_even_bits(bad)


@pytest.mark.parametrize("bad", [True, False])
def test_bool_raises_type_error(bad):
    """Booleans must be rejected even though ``bool`` is a subclass of ``int``."""
    with pytest.raises(TypeError):
        swap_odd_even_bits(bad)