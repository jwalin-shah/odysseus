"""Tests for winsorized_mean."""
import math
import pytest

from stats_utils.winsorized_mean import winsorized_mean


def test_winsorized_mean_basic():
    """Basic winsorized mean should cap extreme values."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
    # k = int(0.1 * 10) = 1
    # Replace smallest (1) with 2 and largest (100) with 9
    # Winsorized: [2, 2, 3, 4, 5, 6, 7, 8, 9, 9] -> mean = 5.5
    result = winsorized_mean(data, proportion=0.1)
    assert math.isclose(result, 5.5)


def test_winsorized_mean_proportion_clamped_above_half():
    """Proportion above 0.5 must be clamped to 0.5."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    # proportion=0.8 should behave identically to proportion=0.5
    # k = 5: replace bottom 5 with 6, replace top 5 with 5
    # Winsorized: [6, 6, 6, 6, 6, 5, 5, 5, 5, 5] -> mean = 5.5
    result = winsorized_mean(data, proportion=0.8)
    assert math.isclose(result, 5.5)


def test_winsorized_mean_proportion_half_explicit():
    """Proportion of exactly 0.5 should yield the fully winsorized mean."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    result = winsorized_mean(data, proportion=0.5)
    assert math.isclose(result, 5.5)


def test_winsorized_mean_clamped_equals_half():
    """Clamped proportion (>0.5) must equal the 0.5 result."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert math.isclose(
        winsorized_mean(data, proportion=0.99),
        winsorized_mean(data, proportion=0.5),
    )


def test_winsorized_mean_zero_proportion():
    """Zero proportion should return the regular arithmetic mean."""
    data = [1, 2, 3, 4, 5]
    result = winsorized_mean(data, proportion=0)
    assert math.isclose(result, 3.0)


def test_winsorized_mean_empty_raises():
    """Empty data should raise ValueError."""
    with pytest.raises(ValueError):
        winsorized_mean([])


def test_winsorized_mean_invalid_proportion():
    """Proportion outside [0, 1] should raise ValueError."""
    with pytest.raises(ValueError):
        winsorized_mean([1, 2, 3], proportion=-0.1)
    with pytest.raises(ValueError):
        winsorized_mean([1, 2, 3], proportion=1.1)


def test_winsorized_mean_single_element():
    """Single-element input should return that element regardless of proportion."""
    result = winsorized_mean([42], proportion=0.4)
    assert math.isclose(result, 42.0)


def test_winsorized_mean_unsorted_input():
    """Function should sort input internally before winsorizing."""
    data = [10, 1, 9, 2, 8, 3, 7, 4, 6, 5]
    result = winsorized_mean(data, proportion=0.5)
    assert math.isclose(result, 5.5)