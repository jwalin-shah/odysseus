import math
import os
import sys

# Make the src/ package importable when running pytest from the repo root.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from stats_gini import stats_gini


def test_empty_list_returns_zero():
    assert stats_gini([]) == 0.0


def test_single_value_returns_zero():
    assert stats_gini([42]) == 0.0


def test_all_equal_returns_zero():
    assert stats_gini([5, 5, 5, 5, 5]) == 0.0


def test_all_zeros_returns_zero():
    assert stats_gini([0, 0, 0, 0]) == 0.0


def test_two_values():
    # [1, 2]: Gini = 1/6
    assert math.isclose(stats_gini([1, 2]), 1 / 6)


def test_three_values_arithmetic():
    # [1, 2, 3]: Gini = 2/9
    assert math.isclose(stats_gini([1, 2, 3]), 2 / 9)


def test_five_values_arithmetic():
    # [1, 2, 3, 4, 5]: Gini = 4/15
    assert math.isclose(stats_gini([1, 2, 3, 4, 5]), 4 / 15)


def test_perfect_inequality_three_zeros_one_one():
    # [0, 0, 0, 1]: Gini = 3/4
    assert math.isclose(stats_gini([0, 0, 0, 1]), 0.75)


def test_arithmetic_sequence_grows_with_spread():
    # A "tight" distribution: eight 1's and a single 2.
    # Standard Gini = 4/45 (~0.0889).  The previous test assumed 1/9, which
    # is the wrong value for this input; the correct value is 4/45.
    tight = [1, 1, 1, 1, 1, 1, 1, 1, 2]
    spread = [1, 2, 3, 4, 5, 6, 7, 8, 100]
    tight_gini = stats_gini(tight)
    spread_gini = stats_gini(spread)
    assert math.isclose(tight_gini, 4 / 45)
    assert spread_gini > tight_gini


def test_inequality_increases_with_concentration():
    spread = stats_gini([1, 2, 3, 4, 5])
    concentrated = stats_gini([1, 1, 1, 1, 100])
    assert concentrated > spread


def test_unsorted_input_matches_sorted():
    # Function should sort internally, so order of input doesn't matter.
    assert math.isclose(stats_gini([3, 1, 2]), stats_gini([1, 2, 3]))


def test_returns_float():
    assert isinstance(stats_gini([1, 2, 3]), float)


def test_bounded_between_0_and_1():
    # For non-negative inputs the Gini coefficient must lie in [0, 1).
    result = stats_gini([1, 5, 3, 9, 2, 7, 4, 8, 6])
    assert 0.0 <= result < 1.0


def test_does_not_mutate_input():
    original = [3, 1, 2]
    snapshot = list(original)
    stats_gini(original)
    assert original == snapshot