"""Pytest suite for ``geometry_tasks.point_to_segment_distance``."""

import math

import pytest

from geometry_tasks.point_to_segment_distance import point_to_segment_distance


def test_point_on_segment_has_zero_distance():
    """A point that lies exactly on the segment has distance 0."""
    assert point_to_segment_distance(
        (1.0, 1.0), (0.0, 0.0), (2.0, 2.0)
    ) == pytest.approx(0.0)


def test_point_at_endpoint_has_zero_distance():
    """The endpoints themselves are at distance 0 from the segment."""
    assert point_to_segment_distance(
        (0.0, 0.0), (0.0, 0.0), (3.0, 4.0)
    ) == pytest.approx(0.0)
    assert point_to_segment_distance(
        (3.0, 4.0), (0.0, 0.0), (3.0, 4.0)
    ) == pytest.approx(0.0)


def test_perpendicular_distance_to_horizontal_segment():
    """Perpendicular distance to a horizontal segment is the y-delta."""
    assert point_to_segment_distance(
        (1.0, 5.0), (0.0, 0.0), (4.0, 0.0)
    ) == pytest.approx(5.0)


def test_closest_point_is_start_when_projection_before_segment():
    """When the perpendicular foot is before A, the closest point is A."""
    # Segment (0,0)-(1,0); point (-1, 5) projects to t=-1.
    d = point_to_segment_distance((-1.0, 5.0), (0.0, 0.0), (1.0, 0.0))
    assert d == pytest.approx(math.sqrt(1.0 + 25.0))


def test_closest_point_is_end_when_projection_after_segment():
    """When the perpendicular foot is past B, the closest point is B."""
    # Segment (0,0)-(2,0); point (10, 3) projects to t=5.
    d = point_to_segment_distance((10.0, 3.0), (0.0, 0.0), (2.0, 0.0))
    assert d == pytest.approx(math.sqrt(64.0 + 9.0))


def test_diagonal_segment_distance():
    """Distance from (0, 5) to the segment (0,0)-(5,5) is sqrt(12.5)."""
    d = point_to_segment_distance((0.0, 5.0), (0.0, 0.0), (5.0, 5.0))
    assert d == pytest.approx(math.sqrt(12.5))


def test_degenerate_segment_returns_point_to_point_distance():
    """A zero-length segment behaves like a single point."""
    d = point_to_segment_distance((3.0, 4.0), (0.0, 0.0), (0.0, 0.0))
    assert d == pytest.approx(5.0)


def test_works_in_3d():
    """The function is correct for 3-dimensional points and segments."""
    # Point on the segment.
    assert point_to_segment_distance(
        (1, 1, 3), (1, 1, 1), (1, 1, 5)
    ) == pytest.approx(0.0)
    # Point off the segment, projection lands on the segment.
    assert point_to_segment_distance(
        (4, 5, 3), (1, 1, 1), (1, 1, 5)
    ) == pytest.approx(5.0)
    # Point off the segment, closest endpoint is the start.
    assert point_to_segment_distance(
        (0, 0, 0), (1, 1, 1), (1, 1, 5)
    ) == pytest.approx(math.sqrt(3.0))


def test_accepts_lists_as_well_as_tuples():
    """Any sequence of coordinates is acceptable, not just tuples."""
    d_tuple = point_to_segment_distance((1.0, 5.0), (0, 0), [4, 0])
    d_list = point_to_segment_distance([1.0, 5.0], (0, 0), (4, 0))
    assert d_tuple == pytest.approx(d_list)
    assert d_tuple == pytest.approx(5.0)


def test_dimension_mismatch_raises_value_error():
    """Mismatched dimensions should raise ``ValueError``."""
    with pytest.raises(ValueError):
        point_to_segment_distance((1.0, 2.0), (0, 0, 0), (1, 1, 1))
    with pytest.raises(ValueError):
        point_to_segment_distance((1.0, 2.0, 3.0), (0, 0), (1, 1))