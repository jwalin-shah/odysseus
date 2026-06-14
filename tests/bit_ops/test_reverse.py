import os
import sys

import pytest

# Ensure the repository root is on sys.path so `bit_ops` is importable
# when pytest is invoked from any working directory.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from bit_ops.reverse import reverse  # noqa: E402


class TestReverseBasic:
    def test_reverse_zero(self):
        # 0 in binary is "0"; reversing yields 0.
        assert reverse(0) == 0

    def test_reverse_one(self):
        # 0b1 reversed is 0b1.
        assert reverse(1) == 1

    def test_reverse_known_example(self):
        # 0b1101 (13) -> 0b1011 (11)
        assert reverse(0b1101) == 0b1011
        assert reverse(13) == 11

    def test_reverse_larger_example(self):
        # 0b1011001 (89) -> 0b1001101 (77)
        assert reverse(0b1011001) == 0b1001101
        assert reverse(89) == 77

    def test_reverse_returns_int(self):
        result = reverse(13)
        assert isinstance(result, int)
        assert result == 11

    def test_reverse_palindrome(self):
        # Binary palindromes should reverse to themselves.
        # 0b101 (5) reversed is 0b101 (5)
        # 0b1001 (9) reversed is 0b1001 (9)
        # 0b11011 (27) reversed is 0b11011 (27)
        assert reverse(0b101) == 0b101
        assert reverse(5) == 5
        assert reverse(0b1001) == 0b1001
        assert reverse(9) == 9
        assert reverse(0b11011) == 0b11011
        assert reverse(27) == 27

    def test_reverse_two(self):
        # 0b10 (2) reversed is 0b01 (1)
        assert reverse(2) == 1
        assert reverse(0b10) == 0b1

    def test_reverse_three(self):
        # 0b11 (3) reversed is 0b11 (3) -- palindrome
        assert reverse(3) == 3

    def test_reverse_four(self):
        # 0b100 (4) reversed is 0b001 (1)
        assert reverse(4) == 1
        assert reverse(0b100) == 0b1

    def test_reverse_seven(self):
        # 0b111 (7) reversed is 0b111 (7) -- palindrome
        assert reverse(7) == 7

    def test_reverse_eight(self):
        # 0b1000 (8) reversed is 0b0001 (1)
        assert reverse(8) == 1

    def test_reverse_power_of_two(self):
        # Any 2^k has binary "1" followed by k zeros, which reverses to 1.
        assert reverse(16) == 1
        assert reverse(32) == 1
        assert reverse(1024) == 1

    def test_reverse_2n_minus_1(self):
        # Numbers of form 2^n - 1 are all-ones in binary and are palindromes.
        assert reverse(0b1111) == 0b1111
        assert reverse(15) == 15
        assert reverse(31) == 31
        assert reverse(255) == 255

    def test_reverse_all_ones_bit_count(self):
        # The reversed value has the same number of 1-bits as the original.
        for n in [0, 1, 13, 89, 1023]:
            assert bin(reverse(n)).count("1") == bin(n).count("1")


class TestReverseErrors:
    def test_reverse_negative_raises(self):
        with pytest.raises(ValueError):
            reverse(-1)

    def test_reverse_large_negative_raises(self):
        with pytest.raises(ValueError):
            reverse(-100)

    def test_reverse_string_raises(self):
        with pytest.raises(TypeError):
            reverse("13")

    def test_reverse_float_raises(self):
        with pytest.raises(TypeError):
            reverse(1.5)

    def test_reverse_none_raises(self):
        with pytest.raises(TypeError):
            reverse(None)

    def test_reverse_list_raises(self):
        with pytest.raises(TypeError):
            reverse([1, 0, 1])

    def test_reverse_bool_true_raises(self):
        # bool is a subclass of int in Python, but spec rejects it.
        with pytest.raises(TypeError):
            reverse(True)

    def test_reverse_bool_false_raises(self):
        with pytest.raises(TypeError):
            reverse(False)