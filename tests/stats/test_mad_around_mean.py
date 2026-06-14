"""Tests for :func:`stats.mad_around_mean.mad_around_mean`."""

import math

import pytest

from stats.mad_around_mean import mad_around_mean


def test_basic_integers():
    # mean([1, 2, 3, 4, 5]) == 3.0
    # absolute deviations: 2, 1, 0, 1, 2  ->  sum = 6  ->  MAD = 1.2
    assert math.isclose(mad_around_mean([1, 2, 3, 4, 5]), 1.2)


def test_symmetric_around_zero():
    # mean = 0, deviations: 3, 1, 1, 3 -> sum = 8 -> MAD = 2.0
    assert math.isclose(mad_around_mean([-3, -1, 1, 3]), 2.0)


def test_constant_values_have_zero_mad():
    assert math.isclose(mad_around_mean([7, 7, 7, 7, 7]), 0.0)


def test_single_element_has_zero_mad():
    assert mad_around_mean([42]) == 0.0
    assert mad_around_mean([3.14]) == 0.0


def test_empty_input_returns_zero():
    assert mad_around_mean([]) == 0.0


def test_floats():
    # mean = 2.5, deviations: 1, 0, 1 -> sum = 2 -> MAD = 2/3
    assert math.isclose(mad_around_mean([1.5, 2.5, 3.5]), 2.0 / 3.0)


def test_mixed_ints_and_floats():
    # mean = (1 + 2.5 + 4) / 3 = 7.5/3 = 2.5
    # deviations: 1.5, 0, 1.5 -> sum = 3 -> MAD = 1.0
    assert math.isclose(mad_around_mean([1, 2.5, 4]), 1.0)


def test_generator_input_is_consumed_once():
    # The implementation must work on a one-shot iterator by
    # materialising it internally.
    gen = (x for x in [1, 2, 3, 4, 5])
    assert math.isclose(mad_around_mean(gen), 1.2)


def test_non_numeric_element_raises_type_error():
    with pytest.raises(TypeError):
        mad_around_mean([1, 2, "three"])  # type: ignore[list-item]


def test_non_iterable_raises_type_error():
    with pytest.raises(TypeError):
        mad_around_mean(123)  # type: ignore[arg-type]


def test_result_is_float_for_integer_input():
    # Even when the input contains only integers, the returned
    # value should be a ``float`` for consistency.
    result = mad_around_mean([1, 2, 3])
    assert isinstance(result, float)


def test_known_dataset():
    # A classic textbook example.
    data = [2, 4, 6, 8, 10]
    # mean = 6, absolute deviations: 4, 2, 0, 2, 4 -> sum = 12 -> MAD = 2.4
    assert math.isclose(mad_around_mean(data), 2.4)