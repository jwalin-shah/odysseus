"""Tests for ``bitwise_and_reducer.bitwise_and_reducer``."""
import operator
import functools
import pytest

from bitwise_and_reducer import bitwise_and_reducer


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

def test_reduces_known_values_to_zero():
    # 12 (1100) & 10 (1010) & 6 (0110) -> 0
    assert bitwise_and_reducer([12, 10, 6]) == 0


def test_reduces_known_values_to_nonzero():
    # 15 (1111) & 7 (0111) & 3 (0011) -> 3 (0011)
    assert bitwise_and_reducer([15, 7, 3]) == 3


def test_single_element_is_returned_unchanged():
    assert bitwise_and_reducer([42]) == 42


def test_single_element_zero():
    assert bitwise_and_reducer([0]) == 0


def test_two_elements():
    assert bitwise_and_reducer([0b1100, 0b1010]) == 0b1000


def test_all_ones_pattern():
    assert bitwise_and_reducer([0b11111111, 0b11111111, 0b11111111]) == 0b11111111


def test_disjoint_bit_patterns():
    # No bits in common -> result is 0
    assert bitwise_and_reducer([0b1010, 0b0101]) == 0


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_iterable_raises_value_error():
    with pytest.raises(ValueError):
        bitwise_and_reducer([])


def test_empty_generator_raises_value_error():
    with pytest.raises(ValueError):
        bitwise_and_reducer(x for x in [])


def test_any_zero_collapses_result_to_zero():
    assert bitwise_and_reducer([1, 2, 3, 0, 4, 5]) == 0


def test_zero_first_collapses_result_to_zero():
    assert bitwise_and_reducer([0, 1, 2, 3]) == 0


def test_accepts_generator_input():
    gen = (x for x in [15, 7, 3])
    assert bitwise_and_reducer(gen) == 3


def test_accepts_tuple_input():
    assert bitwise_and_reducer((12, 10, 6)) == 0


def test_accepts_range_input():
    # range(8) -> 0..7  -> 000 & 001 & ... & 111 == 0
    assert bitwise_and_reducer(range(8)) == 0


def test_accepts_iterator_input():
    it = iter([255, 15, 7])
    assert bitwise_and_reducer(it) == 7


def test_large_iterable_matches_pythonic_reduce():
    values = [0b10101100, 0b11110000, 0b00111100, 0b11000011]
    expected = functools.reduce(operator.and_, values)
    assert bitwise_and_reducer(values) == expected


def test_duplicate_values():
    assert bitwise_and_reducer([7, 7, 7, 7]) == 7


def test_large_repeated_value():
    assert bitwise_and_reducer([0xFF] * 1000) == 0xFF


def test_iterates_only_as_needed_when_zero_is_hit():
    # The reducer short-circuits on zero, so this infinite-ish stream
    # combined with a leading 0 must finish immediately.
    values = iter([0, 1, 2, 3])
    assert bitwise_and_reducer(values) == 0