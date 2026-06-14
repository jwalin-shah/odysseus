"""Tests for ``interval_jaccard``."""
import math

import pytest

from interval_jaccard import interval_jaccard


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

def test_identical_intervals_have_jaccard_one():
    """Two identical intervals must score 1.0."""
    assert interval_jaccard((0, 10), (0, 10)) == 1.0


def test_partial_overlap_returns_expected_fraction():
    """Partial overlap returns ``len(intersection) / len(union)``."""
    # [0, 10] ∩ [5, 15] = [5, 10] (length 5)
    # [0, 10] ∪ [5, 15] = [0, 15] (length 15)
    # Jaccard = 5 / 15 = 1/3
    assert math.isclose(interval_jaccard((0, 10), (5, 15)), 1 / 3)


def test_disjoint_intervals_have_jaccard_zero():
    """Disjoint intervals share no length, so the Jaccard is 0."""
    assert interval_jaccard((0, 5), (10, 15)) == 0.0


def test_one_interval_contains_the_other():
    """When one interval contains the other, Jaccard == inner / outer."""
    # [0, 10] contains [2, 5]: intersection length 3, union length 10.
    assert math.isclose(interval_jaccard((0, 10), (2, 5)), 0.3)


def test_touching_at_a_point_have_jaccard_zero():
    """Closed intervals touching at a single point have measure-zero overlap."""
    assert interval_jaccard((0, 5), (5, 10)) == 0.0


# ---------------------------------------------------------------------------
# Symmetry & input flexibility
# ---------------------------------------------------------------------------

def test_order_of_arguments_does_not_matter():
    """The Jaccard index is symmetric in its arguments."""
    a = interval_jaccard((0, 10), (5, 15))
    b = interval_jaccard((5, 15), (0, 10))
    assert math.isclose(a, b)


def test_list_input_works_like_tuple():
    """Lists should be accepted just like tuples."""
    assert interval_jaccard([0, 10], [0, 10]) == 1.0
    assert math.isclose(interval_jaccard([0, 10], [5, 15]), 1 / 3)


def test_float_intervals():
    """The function handles floating-point endpoints."""
    # [0.0, 1.0] ∩ [0.5, 1.5] = [0.5, 1.0] (length 0.5)
    # [0.0, 1.0] ∪ [0.5, 1.5] = [0.0, 1.5] (length 1.5)
    # Jaccard = 0.5 / 1.5 = 1/3
    assert math.isclose(interval_jaccard((0.0, 1.0), (0.5, 1.5)), 1 / 3)


# ---------------------------------------------------------------------------
# Degenerate (zero-length) intervals
# ---------------------------------------------------------------------------

def test_zero_length_intervals_at_same_point_are_identical():
    """Two coincident points are the same singleton set -> Jaccard 1.0."""
    assert interval_jaccard((5, 5), (5, 5)) == 1.0


def test_zero_length_intervals_at_different_points_are_disjoint():
    """Two distinct points are disjoint -> Jaccard 0.0."""
    assert interval_jaccard((5, 5), (10, 10)) == 0.0


def test_zero_length_point_inside_positive_interval():
    """A point inside a positive-length interval fully overlaps it -> 1.0."""
    assert interval_jaccard((5, 5), (0, 10)) == 1.0


def test_zero_length_point_outside_positive_interval():
    """A point outside a positive-length interval is disjoint -> 0.0."""
    assert interval_jaccard((15, 15), (0, 10)) == 0.0


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_invalid_interval_raises_value_error():
    """``start > end`` is a malformed interval and must raise ValueError."""
    with pytest.raises(ValueError):
        interval_jaccard((10, 0), (0, 10))


def test_malformed_input_raises_type_error():
    """Non-sequence inputs must raise TypeError, not silently misbehave."""
    with pytest.raises(TypeError):
        interval_jaccard(1, (0, 10))