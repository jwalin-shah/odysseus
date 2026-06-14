"""Tests for ``geometry_tasks_point_to_segment_distance.point_to_segment_distance``."""

from __future__ import annotations

import math
import os
import sys

import pytest

# Make the ``src`` directory importable when pytest is run from the repo root.
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from geometry_tasks_point_to_segment_distance import point_to_segment_distance  # noqa: E402


# ---------------------------------------------------------------------------
# 2D tests
# ---------------------------------------------------------------------------


def test_perpendicular_distance_to_horizontal_segment():
    """A point directly above a horizontal segment hits the interior."""
    # Segment from (0, 0) to (10, 0); point at (5, 3) -> distance 3.
    assert math.isclose(
        point_to_segment_distance((5, 3), (0, 0), (10, 0)),
        3.0,
    )


def test_distance_when_projection_falls_before_start():
    """Projection past the start endpoint uses the start as closest point."""
    # Segment from (0, 0) to (10, 0); point at (-3, 4) -> closest (0, 0) -> 5.
    assert math.isclose(
        point_to_segment_distance((-3, 4), (0, 0), (10, 0)),
        5.0,
    )


def test_distance_when_projection_falls_past_end():
    """Projection past the end endpoint uses the end as closest point."""
    # Segment from (0, 0) to (10, 0); point at (13, -4) -> closest (10, 0) -> 5.
    assert math.isclose(
        point_to_segment_distance((13, -4), (0, 0), (10, 0)),
        5.0,
    )


def test_point_on_segment_returns_zero():
    """A point lying on the segment has distance 0."""
    assert math.isclose(
        point_to_segment_distance((3.0, 0.0), (0.0, 0.0), (10.0, 0.0)),
        0.0,
        abs_tol=1e-12,
    )


def test_point_at_segment_start_returns_zero():
    assert math.isclose(
        point_to_segment_distance((0, 0), (0, 0), (10, 0)),
        0.0,
    )


def test_point_at_segment_end_returns_zero():
    assert math.isclose(
        point_to_segment_distance((10, 0), (0, 0), (10, 0)),
        0.0,
    )


def test_degenerate_segment_2d():
    """A zero-length segment is just a point; distance is to that point."""
    # Point (3, 4) to vertex (0, 0) is 5.
    assert math.isclose(
        point_to_segment_distance((3, 4), (0, 0), (0, 0)),
        5.0,
    )


def test_diagonal_segment_2d():
    """Distance to a diagonal segment whose perpendicular foot is interior."""
    # Segment from (0, 0) to (3, 4); point (0, 5).
    # t = (0*3 + 5*4) / 25 = 0.8.  Closest = (2.4, 3.2).  Distance = 3.
    assert math.isclose(
        point_to_segment_distance((0, 5), (0, 0), (3, 4)),
        3.0,
    )


def test_negative_coordinates_2d():
    """Negative coordinates must not change the result."""
    # Segment from (-5, -5) to (-1, -5); point (-3, -10) -> distance 5.
    assert math.isclose(
        point_to_segment_distance((-3, -10), (-5, -5), (-1, -5)),
        5.0,
    )


def test_list_inputs_2d():
    """Lists (not just tuples) should be accepted as input."""
    assert math.isclose(
        point_to_segment_distance([5, 3], [0, 0], [10, 0]),
        3.0,
    )


# ---------------------------------------------------------------------------
# 3D tests
# ---------------------------------------------------------------------------


def test_perpendicular_distance_3d():
    """3D case where the perpendicular foot lies on the segment interior."""
    # Segment along the x-axis; point (5, 3, 4) -> distance sqrt(3^2 + 4^2) = 5.
    assert math.isclose(
        point_to_segment_distance((5, 3, 4), (0, 0, 0), (10, 0, 0)),
        5.0,
    )


def test_projection_outside_segment_3d():
    """3D case where the projection falls past the end of the segment."""
    # Segment from (0, 0, 0) to (1, 0, 0); point (-1, 0, 5).
    # Closest is (0, 0, 0); distance = sqrt(1 + 25) = sqrt(26).
    assert math.isclose(
        point_to_segment_distance((-1, 0, 5), (0, 0, 0), (1, 0, 0)),
        math.sqrt(26.0),
    )


def test_degenerate_segment_3d():
    """A zero-length 3D segment behaves like a single point."""
    # Point (1, 2, 2) to vertex (1, 2, 2) is 0.
    assert math.isclose(
        point_to_segment_distance((1, 2, 2), (1, 2, 2), (1, 2, 2)),
        0.0,
    )


def test_non_axis_aligned_segment_3d():
    """Distance to a generic 3D segment whose foot falls at an endpoint."""
    # Segment from (1, 1, 1) to (4, 5, 1); point (1, 1, 9).
    # The foot of the perpendicular is (1, 1, 1) (t = 0); distance = 8.
    assert math.isclose(
        point_to_segment_distance((1, 1, 9), (1, 1, 1), (4, 5, 1)),
        8.0,
    )


# ---------------------------------------------------------------------------
# General / error-handling tests
# ---------------------------------------------------------------------------


def test_result_is_always_non_negative():
    """Distance must never be negative regardless of input orientation."""
    samples = [
        ((5, 3), (0, 0), (10, 0)),
        ((-3, 4), (0, 0), (10, 0)),
        ((0, 5), (0, 0), (3, 4)),
        ((5, 3, 4), (0, 0, 0), (10, 0, 0)),
        ((-1, 0, 5), (0, 0, 0), (1, 0, 0)),
    ]
    for p, a, b in samples:
        assert point_to_segment_distance(p, a, b) >= 0.0


def test_distance_is_symmetric_in_segment_endpoints():
    """Swapping the segment endpoints must not change the distance."""
    assert math.isclose(
        point_to_segment_distance((2, 7), (1, 2), (6, 4)),
        point_to_segment_distance((2, 7), (6, 4), (1, 2)),
    )


def test_mismatched_dimensions_raises():
    """A 2D point queried against a 3D segment must raise ``ValueError``."""
    with pytest.raises(ValueError):
        point_to_segment_distance((0, 0), (0, 0, 0), (1, 1, 1))


def test_unsupported_dimension_raises():
    """A 1D or 4D point is not supported and must raise ``ValueError``."""
    with pytest.raises(ValueError):
        point_to_segment_distance((1.0,), (0.0,), (5.0,))
    with pytest.raises(ValueError):
        point_to_segment_distance(
            (0, 0, 0, 0), (0, 0, 0, 0), (1, 1, 1, 1)
        )