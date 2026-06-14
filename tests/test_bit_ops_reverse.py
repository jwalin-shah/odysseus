import os
import sys

import pytest

# Allow running the tests from the repo root without installing the package.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.bit_ops_reverse import bit_ops_reverse, popcount


class TestBasic:
    def test_zero(self):
        assert bit_ops_reverse(0) == 0

    def test_one(self):
        assert bit_ops_reverse(1) == 1

    def test_two(self):
        # 10 -> 01
        assert bit_ops_reverse(2) == 1

    def test_three(self):
        # 11 -> 11 (palindrome)
        assert bit_ops_reverse(3) == 3

    def test_twelve(self):
        # 1100 -> 0011
        assert bit_ops_reverse(12) == 3

    def test_known_value_with_fixed_width(self):
        # 00001100 (8 bits) -> 00110000 = 48
        assert bit_ops_reverse(12, 8) == 48

    def test_full_byte_reversal(self):
        # 10000000 (8 bits) -> 00000001 = 1
        assert bit_ops_reverse(128, 8) == 1

    def test_palindromic_powers_of_two(self):
        # 1, 3, 7, 15, ... are all 1-bits and reverse to themselves.
        for k in range(0, 10):
            value = (1 << (k + 1)) - 1
            assert bit_ops_reverse(value) == value


class TestInvolution:
    def test_reverse_is_involution_default(self):
        # Reversing twice returns the original for many widths.
        for value in [0, 1, 2, 3, 5, 6, 12, 27, 170, 255, 1023]:
            once = bit_ops_reverse(value)
            twice = bit_ops_reverse(once, bit_width=value.bit_length() or 1)
            assert twice == value

    def test_roundtrip_fixed_width(self):
        for value in [0, 1, 2, 3, 12, 27, 170, 255, 1023, 65535]:
            assert bit_ops_reverse(bit_ops_reverse(value, 16), 16) == value


class TestPopcount:
    def test_popcount_preserved(self):
        for value in [0, 1, 2, 3, 4, 5, 6, 7, 12, 27, 170, 255, 1023, 12345]:
            assert popcount(bit_ops_reverse(value)) == popcount(value)

    def test_popcount_preserved_fixed_width(self):
        for value in [0, 1, 2, 3, 12, 27, 170, 255, 1023, 12345]:
            assert popcount(bit_ops_reverse(value, 16)) == popcount(value)


class TestEdgeCases:
    def test_zero_with_explicit_width(self):
        assert bit_ops_reverse(0, 8) == 0

    def test_one_with_explicit_width(self):
        # 00000001 -> 10000000 = 128
        assert bit_ops_reverse(1, 8) == 128

    def test_rejects_negative(self):
        with pytest.raises(ValueError):
            bit_ops_reverse(-1)

    def test_rejects_non_int(self):
        with pytest.raises(TypeError):
            bit_ops_reverse("5")  # type: ignore[arg-type]

    def test_rejects_zero_width(self):
        with pytest.raises(ValueError):
            bit_ops_reverse(5, 0)

    def test_rejects_bool(self):
        # bool is a subclass of int but we want to forbid it.
        with pytest.raises(TypeError):
            bit_ops_reverse(True)  # type: ignore[arg-type]


class TestRandomized:
    @pytest.mark.parametrize("value", [0, 1, 2, 3, 5, 7, 10, 42, 100, 255, 1000, 8191])
    def test_popcount_invariant(self, value):
        assert popcount(bit_ops_reverse(value)) == popcount(value)

    @pytest.mark.parametrize("value", [0, 1, 2, 3, 5, 7, 10, 42, 100, 255, 1000, 8191])
    def test_double_reversal_default(self, value):
        w = value.bit_length() or 1
        assert bit_ops_reverse(bit_ops_reverse(value, w), w) == value