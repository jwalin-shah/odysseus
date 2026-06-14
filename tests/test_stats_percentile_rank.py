import os
import sys

# Make the src/ package importable when tests are run from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from src.stats_percentile_rank import percentile_rank


def test_basic_midpoint_rank():
    """The midpoint of a sorted list should sit near the 50th percentile."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    # x = 5: L = 4 (1..4), S = 1, N = 10 -> (4 + 0.5)/10 * 100 = 45.0
    assert percentile_rank(data, 5) == 45.0


def test_value_below_all_data_is_zero():
    """A value below the minimum of the data should have rank 0."""
    data = [10, 20, 30, 40, 50]
    assert percentile_rank(data, 5) == 0.0


def test_value_above_all_data_is_full_rank():
    """A value above the maximum of the data should have rank 100."""
    data = [1, 2, 3, 4, 5]
    assert percentile_rank(data, 100) == 100.0


def test_rank_is_bounded_between_zero_and_hundred():
    """Percentile rank must always lie in the closed interval [0, 100]."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    for x in [-50, 0, 0.5, 1, 5, 10, 11, 12, 100, 1000]:
        rank = percentile_rank(data, x)
        assert 0.0 <= rank <= 100.0, f"rank {rank} out of bounds for x={x}"


def test_empty_data_raises_value_error():
    """An empty dataset should raise a ValueError."""
    with pytest.raises(ValueError):
        percentile_rank([], 5)


def test_none_data_raises_value_error():
    """A None dataset should raise a ValueError."""
    with pytest.raises(ValueError):
        percentile_rank(None, 5)  # type: ignore[arg-type]


def test_single_element_dataset():
    """With a single element, that element is at the 50th percentile."""
    data = [42]
    # x == data[0]: L = 0, S = 1, N = 1 -> (0 + 0.5)/1 * 100 = 50.0
    assert percentile_rank(data, 42) == 50.0
    assert percentile_rank(data, 10) == 0.0
    assert percentile_rank(data, 100) == 100.0


def test_duplicate_values():
    """Duplicates should be handled via the S (count-equal) term."""
    data = [1, 2, 2, 3, 4]
    # x = 2: L = 1 (only 1 < 2), S = 2, N = 5 -> (1 + 1)/5 * 100 = 40.0
    assert percentile_rank(data, 2) == 40.0
    # x = 3: L = 3 (1, 2, 2), S = 1, N = 5 -> (3 + 0.5)/5 * 100 = 70.0
    assert percentile_rank(data, 3) == 70.0


def test_all_identical_values():
    """When every value is the same, querying that value yields 50."""
    data = [5, 5, 5, 5, 5]
    # x = 5: L = 0, S = 5, N = 5 -> (0 + 2.5)/5 * 100 = 50.0
    assert percentile_rank(data, 5) == 50.0
    assert percentile_rank(data, 3) == 0.0
    assert percentile_rank(data, 10) == 100.0


def test_minimum_and_maximum_of_dataset():
    """The minimum yields a small rank, the maximum yields a large one."""
    data = [1, 2, 3, 4, 5]
    # min: L = 0, S = 1, N = 5 -> 0.5/5 * 100 = 10.0
    assert percentile_rank(data, 1) == 10.0
    # max: L = 4, S = 1, N = 5 -> 4.5/5 * 100 = 90.0
    assert percentile_rank(data, 5) == 90.0


def test_unsorted_input_is_handled():
    """The function should not depend on the input being pre-sorted."""
    data = [5, 1, 3, 2, 4]
    # Same multiset as the sorted [1,2,3,4,5], so x=3 should give 50.0.
    # x = 3: L = 2 (1, 2), S = 1, N = 5 -> 2.5/5 * 100 = 50.0
    assert percentile_rank(data, 3) == 50.0


def test_returns_float():
    """The return type should be float."""
    rank = percentile_rank([1, 2, 3], 2)
    assert isinstance(rank, float)