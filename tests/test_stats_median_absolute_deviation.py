import math
import pytest

from src.stats_median_absolute_deviation import stats_median_absolute_deviation


def test_returns_float():
    """The result must always be a float."""
    result = stats_median_absolute_deviation([1, 2, 3, 4])
    assert isinstance(result, float)


def test_simple_case():
    """MAD of [1, 1, 2, 2, 4, 6, 9] is 1 (well-known example)."""
    data = [1, 1, 2, 2, 4, 6, 9]
    result = stats_median_absolute_deviation(data)
    assert math.isclose(result, 1.0, rel_tol=1e-9)


def test_all_equal_values():
    """If all values are equal, the MAD should be 0.0."""
    data = [5, 5, 5, 5, 5]
    result = stats_median_absolute_deviation(data)
    assert result == 0.0


def test_empty_input():
    """Empty input should return 0.0 rather than raising."""
    result = stats_median_absolute_deviation([])
    assert result == 0.0


def test_single_value():
    """A single-element input should return 0.0."""
    result = stats_median_absolute_deviation([42])
    assert result == 0.0


def test_two_values():
    """Two-value input: median is the average, deviations are symmetric."""
    data = [2, 8]
    # median = 5.0, deviations = [3, 3], MAD = 3.0
    result = stats_median_absolute_deviation(data)
    assert math.isclose(result, 3.0, rel_tol=1e-9)


def test_even_length_known_value():
    """Even-length data point: median = mean of two middle values."""
    data = [1, 2, 3, 4]
    # median = 2.5, deviations = [1.5, 0.5, 0.5, 1.5] sorted -> [0.5, 0.5, 1.5, 1.5]
    # MAD = (0.5 + 1.5)/2 = 1.0
    result = stats_median_absolute_deviation(data)
    assert math.isclose(result, 1.0, rel_tol=1e-9)


def test_negative_values():
    """The function should work correctly with negative numbers."""
    data = [-4, -2, 0, 2, 4]
    # median = 0, deviations = [4, 2, 0, 2, 4], MAD = 2
    result = stats_median_absolute_deviation(data)
    assert math.isclose(result, 2.0, rel_tol=1e-9)


def test_does_not_mutate_input():
    """The function must not mutate the caller's list."""
    data = [3, 1, 2]
    snapshot = list(data)
    stats_median_absolute_deviation(data)
    assert data == snapshot


def test_floats_input():
    """A list of floats should be handled correctly."""
    data = [1.5, 2.5, 3.5]
    # median = 2.5, deviations = [1.0, 0.0, 1.0], MAD = 1.0
    result = stats_median_absolute_deviation(data)
    assert math.isclose(result, 1.0, rel_tol=1e-9)
    assert isinstance(result, float)


def test_tuple_input():
    """A tuple should also be accepted as input."""
    data = (10, 20, 30)
    # median = 20, deviations = [10, 0, 10], MAD = 10
    result = stats_median_absolute_deviation(data)
    assert math.isclose(result, 10.0, rel_tol=1e-9)
    assert isinstance(result, float)


def test_outlier_robustness():
    """MAD is robust to a single large outlier relative to a tight cluster."""
    data = [1, 1, 1, 1, 1, 1000]
    # median = 1.0, deviations = [0,0,0,0,0,999], MAD = 0
    result = stats_median_absolute_deviation(data)
    assert math.isclose(result, 0.0, rel_tol=1e-9)