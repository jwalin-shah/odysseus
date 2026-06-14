import math

import pytest

from stats_utils.interquartile_mean import interquartile_mean


def test_two_values():
    # n = 2, k = 0 -> keep [1, 2], mean = 1.5
    assert math.isclose(interquartile_mean([1, 2]), 1.5)


def test_three_values():
    # n = 3, k = 0 -> keep [1, 2, 3], mean = 2.0
    assert math.isclose(interquartile_mean([1, 2, 3]), 2.0)


def test_four_values():
    # n = 4, k = 1 -> keep [2, 3], mean = 2.5
    assert math.isclose(interquartile_mean([1, 2, 3, 4]), 2.5)


def test_five_values():
    # n = 5, k = 1 -> keep [2, 3, 4], mean = 3.0
    assert math.isclose(interquartile_mean([1, 2, 3, 4, 5]), 3.0)


def test_eight_values():
    # n = 8, k = 2 -> keep [3, 4, 5, 6], mean = 4.5
    assert math.isclose(interquartile_mean([1, 2, 3, 4, 5, 6, 7, 8]), 4.5)


def test_single_value():
    assert interquartile_mean([42]) == 42.0


def test_empty_raises():
    with pytest.raises(ValueError):
        interquartile_mean([])


def test_unsorted_input():
    # Order should not affect the result.
    assert math.isclose(interquartile_mean([3, 1, 2]), 2.0)


def test_all_same_values():
    assert interquartile_mean([5, 5, 5, 5, 5]) == 5.0


def test_negative_values():
    # [-4, -3, -2, -1, 0, 1, 2, 3], k = 2 -> keep [-2, -1, 0, 1], mean = -0.5
    assert math.isclose(interquartile_mean([-4, -3, -2, -1, 0, 1, 2, 3]), -0.5)


def test_large_dataset():
    # [1, 2, ..., 100], k = 25 -> keep [26, 27, ..., 75], mean = 50.5
    data = list(range(1, 101))
    assert math.isclose(interquartile_mean(data), 50.5)


def test_floats():
    # n = 4, k = 1 -> keep [2.0, 3.0], mean = 2.5
    assert math.isclose(interquartile_mean([1.0, 2.0, 3.0, 4.0]), 2.5)