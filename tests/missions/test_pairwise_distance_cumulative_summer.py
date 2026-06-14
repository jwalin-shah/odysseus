"""Tests for ``missions.pairwise_distance_cumulative_summer``."""

from __future__ import annotations

import os
import sys

# Make the ``missions`` package importable when tests are executed directly
# (e.g. ``pytest tests/missions``) rather than from the repo root.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from missions.pairwise_distance_cumulative_summer import (
    pairwise_distance_cumulative_summer,
)


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------


def test_strictly_increasing_sequence():
    # |1-4| = 3, |4-7| = 3, |7-10| = 3  ->  cumulative: 3, 6, 9
    assert pairwise_distance_cumulative_summer([1, 4, 7, 10]) == [3, 6, 9]


def test_strictly_decreasing_sequence():
    # Distances are symmetric, result must match the increasing case.
    assert pairwise_distance_cumulative_summer([10, 7, 4, 1]) == [3, 6, 9]


def test_two_elements():
    assert pairwise_distance_cumulative_summer([5, 2]) == [3]


def test_mixed_sequence():
    # |1-5| = 4, |5-2| = 3, |2-8| = 6  ->  cumulative: 4, 7, 13
    assert pairwise_distance_cumulative_summer([1, 5, 2, 8]) == [4, 7, 13]


def test_output_length_is_n_minus_one():
    seq = [0, 3, 1, 7, 2, 9, 4]
    result = pairwise_distance_cumulative_summer(seq)
    assert len(result) == len(seq) - 1


def test_final_value_is_total_distance():
    seq = [0, 3, 1, 7, 2]
    # |0-3|=3, |3-1|=2, |1-7|=6, |7-2|=5  ->  total = 16
    result = pairwise_distance_cumulative_summer(seq)
    assert result[-1] == 16
    assert result == [3, 5, 11, 16]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_sequence_returns_empty_list():
    assert pairwise_distance_cumulative_summer([]) == []


def test_single_element_returns_empty_list():
    assert pairwise_distance_cumulative_summer([42]) == []


def test_identical_consecutive_values_yield_zero_distances():
    # Any pair of equal neighbours contributes 0 to the running total.
    assert pairwise_distance_cumulative_summer([5, 5, 5, 5]) == [0, 0, 0]


def test_negative_values_are_handled():
    # |-3 - 2| = 5, |2 - (-1)| = 3, |-1 - 4| = 5  ->  cumulative: 5, 8, 13
    assert pairwise_distance_cumulative_summer([-3, 2, -1, 4]) == [5, 8, 13]


def test_floating_point_values():
    result = pairwise_distance_cumulative_summer([1.5, 3.0, 2.5, 0.0])
    # |1.5-3.0|=1.5, |3.0-2.5|=0.5, |2.5-0.0|=2.5
    # cumulative: 1.5, 2.0, 4.5
    assert result == [1.5, 2.0, 4.5]


def test_tuple_input_is_accepted():
    # Iterables other than lists should work the same way.
    assert pairwise_distance_cumulative_summer((1, 4, 7)) == [3, 6]


def test_generator_input_is_accepted():
    # Generators are single-pass iterables; the function should still work.
    gen = (x for x in [2, 5, 1])
    assert pairwise_distance_cumulative_summer(gen) == [3, 7]


# ---------------------------------------------------------------------------
# Monotonicity property
# ---------------------------------------------------------------------------


def test_result_is_non_decreasing_for_non_negative_inputs():
    # Absolute differences are always >= 0, so the cumulative sum cannot shrink.
    seq = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]
    result = pairwise_distance_cumulative_summer(seq)
    for previous, current in zip(result, result[1:]):
        assert current >= previous


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_non_iterable_input_raises_type_error():
    with pytest.raises(TypeError):
        pairwise_distance_cumulative_summer(123)  # type: ignore[arg-type]


def test_non_numeric_values_raise_type_error():
    # Subtraction on strings is undefined; the natural TypeError must surface.
    with pytest.raises(TypeError):
        pairwise_distance_cumulative_summer(["a", "b", "c"])