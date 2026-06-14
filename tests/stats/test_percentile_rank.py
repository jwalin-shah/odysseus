import pytest

from stats.percentile_rank import percentile_rank


def test_basic_middle_value():
    # In [1, 2, 3, 4, 5], four out of five values are <= 4 -> 80.0%
    assert percentile_rank([1, 2, 3, 4, 5], 4) == pytest.approx(80.0)


def test_smallest_value():
    # In [1, 2, 3, 4, 5], one out of five values is <= 1 -> 20.0%
    assert percentile_rank([1, 2, 3, 4, 5], 1) == pytest.approx(20.0)


def test_largest_value():
    # In [1, 2, 3, 4, 5], all five values are <= 5 -> 100.0%
    assert percentile_rank([1, 2, 3, 4, 5], 5) == pytest.approx(100.0)


def test_value_below_minimum():
    # A value smaller than every element gets rank 0
    assert percentile_rank([1, 2, 3, 4, 5], 0) == pytest.approx(0.0)


def test_value_above_maximum():
    # A value larger than every element gets rank 100
    assert percentile_rank([1, 2, 3, 4, 5], 10) == pytest.approx(100.0)


def test_value_not_in_data():
    # A value between two existing elements: 2.5 lies between 2 and 3,
    # so 2 of 5 values are <= 2.5 -> 40.0%
    assert percentile_rank([1, 2, 3, 4, 5], 2.5) == pytest.approx(40.0)


def test_duplicate_values():
    # In [1, 2, 2, 3, 4], three out of five values are <= 2 -> 60.0%
    assert percentile_rank([1, 2, 2, 3, 4], 2) == pytest.approx(60.0)


def test_accepts_generators_and_ranges():
    # range(1, 6) is equivalent to [1, 2, 3, 4, 5]; 4 of 5 are <= 4 -> 80.0%
    assert percentile_rank(range(1, 6), 4) == pytest.approx(80.0)


def test_accepts_generator_expression():
    # A generator expression should also work and produce the same result
    assert percentile_rank((i for i in [1, 2, 3, 4, 5]), 3) == pytest.approx(60.0)


def test_single_value_equal_to_x():
    # A one-element dataset where x equals the element -> 100.0%
    assert percentile_rank([5], 5) == pytest.approx(100.0)


def test_single_value_less_than_x():
    # A one-element dataset where x exceeds the element -> 0.0%
    assert percentile_rank([5], 3) == pytest.approx(0.0)


def test_empty_data_raises_value_error():
    with pytest.raises(ValueError):
        percentile_rank([], 5)


def test_none_data_raises_value_error():
    with pytest.raises(ValueError):
        percentile_rank(None, 5)


def test_float_values():
    # Floats work the same way: 2 of 5 values are <= 2.5 -> 40.0%
    assert percentile_rank([1.0, 2.0, 3.0, 4.0, 5.0], 2.5) == pytest.approx(40.0)


def test_negative_values():
    # In [-5, -3, -1, 0, 1], two of five values are <= -3 -> 40.0%
    assert percentile_rank([-5, -3, -1, 0, 1], -3) == pytest.approx(40.0)


def test_all_identical_values_equal_to_x():
    # All elements equal x -> 100.0%
    assert percentile_rank([5, 5, 5, 5, 5], 5) == pytest.approx(100.0)


def test_all_identical_values_greater_than_x():
    # All elements greater than x -> 0.0%
    assert percentile_rank([5, 5, 5, 5, 5], 3) == pytest.approx(0.0)


def test_unsorted_data():
    # The data does not need to be sorted: in [3, 1, 4, 1, 5, 9, 2, 6]
    # the values <= 5 are 3, 1, 4, 1, 5, 2 (six out of eight) -> 75.0%
    assert percentile_rank([3, 1, 4, 1, 5, 9, 2, 6], 5) == pytest.approx(75.0)


def test_tuple_input():
    # Tuples are valid iterables
    assert percentile_rank((1, 2, 3, 4, 5), 3) == pytest.approx(60.0)


def test_returns_float():
    # The result should always be a float
    result = percentile_rank([1, 2, 3], 2)
    assert isinstance(result, float)