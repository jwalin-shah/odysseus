import os
import sys

import pytest

# Make the ``src`` directory importable regardless of how pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from statistics_trimmed_mean_percentage_trim import (  # noqa: E402
    statistics_trimmed_mean_percentage_trim,
)


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------

def test_basic_10_percent_trim():
    """10% trim on 1..10 removes 1 from each end -> mean 5.5."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    # n=10, k=1, remaining [2,3,4,5,6,7,8,9], sum=44, mean=5.5
    assert statistics_trimmed_mean_percentage_trim(data, 0.1) == 5.5


def test_zero_percent_trim_returns_arithmetic_mean():
    """A 0% trim must equal the ordinary mean."""
    data = [1, 2, 3, 4, 5]
    assert statistics_trimmed_mean_percentage_trim(data, 0) == 3.0


def test_20_percent_trim():
    """20% trim on 1..10 keeps [3..8] -> mean 5.5."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    # n=10, k=2, remaining [3,4,5,6,7,8], sum=33, mean=5.5
    assert statistics_trimmed_mean_percentage_trim(data, 0.2) == 5.5


def test_known_values():
    """Spot-check with a different, easily verifiable dataset."""
    data = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    # n=10, k=1, remaining [20,30,40,50,60,70,80,90], sum=440, mean=55.0
    assert statistics_trimmed_mean_percentage_trim(data, 0.1) == 55.0


def test_default_percentage_is_0_1():
    """The function must default to a 10% trim on each side."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert statistics_trimmed_mean_percentage_trim(data) == 5.5


def test_unsorted_input_is_sorted_internally():
    """Input order should not affect the result."""
    data = [10, 1, 9, 2, 8, 3, 7, 4, 6, 5]
    assert statistics_trimmed_mean_percentage_trim(data, 0.1) == 5.5


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_single_element():
    """A one-element dataset is its own mean for any valid percentage."""
    assert statistics_trimmed_mean_percentage_trim([42], 0.1) == 42.0
    assert statistics_trimmed_mean_percentage_trim([42], 0) == 42.0
    assert statistics_trimmed_mean_percentage_trim([42], 0.49) == 42.0


def test_two_elements_with_49_percent_trim():
    """n=2, percentage=0.49 -> k=0, so both elements are kept."""
    assert statistics_trimmed_mean_percentage_trim([2, 4], 0.49) == 3.0


def test_floating_point_data():
    """The function must work with pure float inputs."""
    data = [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5, 9.5, 10.5]
    # n=10, k=1, sum of [2.5..9.5]=48.0, mean=6.0
    assert statistics_trimmed_mean_percentage_trim(data, 0.1) == 6.0


def test_all_zeros():
    """Trimming an all-zero dataset yields zero."""
    data = [0] * 10
    assert statistics_trimmed_mean_percentage_trim(data, 0.1) == 0.0


def test_robust_to_outliers():
    """A large outlier must be removed by the trimming."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 1000]
    # n=11, k=1, remaining [2,3,4,5,6,7,8,9,10], sum=54, mean=6.0
    assert statistics_trimmed_mean_percentage_trim(data, 0.1) == 6.0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_empty_data_raises_value_error():
    with pytest.raises(ValueError):
        statistics_trimmed_mean_percentage_trim([], 0.1)


def test_negative_percentage_raises_value_error():
    with pytest.raises(ValueError):
        statistics_trimmed_mean_percentage_trim([1, 2, 3, 4, 5], -0.1)


def test_percentage_at_upper_bound_raises_value_error():
    """0.5 is not a valid percentage (would remove the entire dataset)."""
    with pytest.raises(ValueError):
        statistics_trimmed_mean_percentage_trim([1, 2, 3, 4, 5], 0.5)


def test_percentage_above_upper_bound_raises_value_error():
    with pytest.raises(ValueError):
        statistics_trimmed_mean_percentage_trim([1, 2, 3, 4, 5], 0.6)


def test_non_numeric_percentage_raises_type_error():
    with pytest.raises(TypeError):
        statistics_trimmed_mean_percentage_trim([1, 2, 3], "0.1")


def test_boolean_percentage_raises_type_error():
    """Booleans are technically ints in Python, but are not meaningful here."""
    with pytest.raises(TypeError):
        statistics_trimmed_mean_percentage_trim([1, 2, 3], True)


def test_non_numeric_data_raises_type_error():
    with pytest.raises(TypeError):
        statistics_trimmed_mean_percentage_trim([1, 2, "three", 4], 0.1)


def test_none_in_data_raises_type_error():
    with pytest.raises(TypeError):
        statistics_trimmed_mean_percentage_trim([1, 2, None, 4], 0.1)