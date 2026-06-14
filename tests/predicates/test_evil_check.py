"""Tests for the evil_check module."""
import pytest

from predicates.evil_check import (
    evil_check,
    evil_numbers,
    first_n_evil,
    first_n_odious,
    is_evil,
    is_odious,
    odious_numbers,
)


class TestEvilCheckBasics:
    def test_zero_is_evil(self):
        # 0 in binary is "0" -> 0 ones (even) -> evil
        assert is_evil(0) is True
        assert is_odious(0) is False

    def test_one_is_odious(self):
        # 1 in binary is "1" -> 1 one (odd) -> odious
        assert is_evil(1) is False
        assert is_odious(1) is True

    def test_three_is_evil(self):
        # 3 in binary is "11" -> 2 ones (even) -> evil
        assert is_evil(3) is True
        assert is_odious(3) is False

    def test_seven_is_odious(self):
        # 7 in binary is "111" -> 3 ones (odd) -> odious
        assert is_evil(7) is False
        assert is_odious(7) is True

    def test_fifteen_is_evil(self):
        # 15 in binary is "1111" -> 4 ones (even) -> evil
        assert is_evil(15) is True

    def test_evil_check_returns_string(self):
        assert evil_check(0) == "evil"
        assert evil_check(1) == "odious"
        assert evil_check(3) == "evil"
        assert evil_check(7) == "odious"


class TestEvilCheckSequences:
    def test_evil_numbers_up_to_20(self):
        # 0(0), 3(11), 5(101), 6(110), 9(1001), 10(1010),
        # 12(1100), 15(1111), 17(10001), 18(10010), 20(10100)
        assert evil_numbers(20) == [0, 3, 5, 6, 9, 10, 12, 15, 17, 18, 20]

    def test_odious_numbers_up_to_20(self):
        # 1(1), 2(10), 4(100), 7(111), 8(1000), 11(1011),
        # 13(1101), 14(1110), 16(10000), 19(10011)
        assert odious_numbers(20) == [1, 2, 4, 7, 8, 11, 13, 14, 16, 19]

    def test_first_evil_numbers_up_to_20(self):
        # First 11 evil numbers (all evil numbers up to and including 20)
        assert first_n_evil(11) == [0, 3, 5, 6, 9, 10, 12, 15, 17, 18, 20]

    def test_first_odious_numbers_up_to_20(self):
        # First 10 odious numbers (all odious numbers up to and including 20)
        assert first_n_odious(10) == [1, 2, 4, 7, 8, 11, 13, 14, 16, 19]

    def test_evil_and_odious_partition(self):
        # Every non-negative integer is either evil or odious (not both).
        for n in range(50):
            assert is_evil(n) != is_odious(n)

    def test_empty_range(self):
        assert evil_numbers(-1) == []
        assert odious_numbers(-1) == []


class TestEvilCheckErrors:
    def test_negative_raises(self):
        with pytest.raises(ValueError):
            is_evil(-1)

    def test_non_integer_raises(self):
        with pytest.raises(TypeError):
            is_evil(1.5)
        with pytest.raises(TypeError):
            is_evil("3")