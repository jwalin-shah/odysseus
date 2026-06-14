import os
import sys

import pytest

# Ensure the src directory is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from geometry_distance import (
    point_to_segment_distance,
    segment_to_segment_distance,
    segments_intersect,
)


# ---------------------------------------------------------------------------
# point_to_segment_distance
# ---------------------------------------------------------------------------

def test_point_to_segment_distance_perpendicular_foot():
    # Closest point is the foot of the perpendicular inside the segment.
    d = point_to_segment_distance((5, 5), (0, 0), (10, 0))
    assert d == pytest.approx(5.0)


def test_point_to_segment_distance_on_segment():
    d = point_to_segment_distance((5, 0), (0, 0), (10, 0))
    assert d == pytest.approx(0.0)


def test_point_to_segment_distance_beyond_endpoint():
    # Closest point is the far endpoint.
    d = point_to_segment_distance((15, 0), (0, 0), (10, 0))
    assert d == pytest.approx(5.0)


def test_point_to_segment_distance_before_start():
    d = point_to_segment_distance((-3, 4), (0, 0), (10, 0))
    assert d == pytest.approx(5.0)


def test_point_to_segment_distance_degenerate_segment():
    # Zero-length segment: distance is just the point-to-point distance.
    d = point_to_segment_distance((3, 4), (0, 0), (0, 0))
    assert d == pytest.approx(5.0)


def test_point_to_segment_distance_diagonal_segment():
    # Segment from (0,0) to (3,4), point at (3,0) -> distance 2.4
    d = point_to_segment_distance((3, 0), (0, 0), (3, 4))
    assert d == pytest.approx(2.4)


def test_point_to_segment_distance_accepts_lists_and_tuples():
    assert point_to_segment_distance([5, 5], (0, 0), [10, 0]) == pytest.approx(5.0)
    assert point_to_segment_distance((5, 5), [0, 0], (10, 0)) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# segments_intersect
# ---------------------------------------------------------------------------

def test_segments_intersect_proper_crossing():
    assert segments_intersect((0, 0), (10, 10), (0, 10), (10, 0)) is True


def test_segments_intersect_touching_at_endpoint():
    assert segments_intersect((0, 0), (5, 0), (5, 0), (5, 5)) is True


def test_segments_intersect_collinear_overlap():
    assert segments_intersect((0, 0), (10, 0), (5, 0), (15, 0)) is True


def test_segments_intersect_disjoint():
    assert segments_intersect((0, 0), (1, 0), (2, 0), (3, 0)) is False


def test_segments_intersect_parallel():
    assert segments_intersect((0, 0), (10, 0), (0, 1), (10, 1)) is False


# ---------------------------------------------------------------------------
# segment_to_segment_distance
# ---------------------------------------------------------------------------

def test_segment_to_segment_distance_intersecting():
    # X-shaped crossing at the origin -> distance 0.
    d = segment_to_segment_distance((0, 0), (10, 10), (0, 10), (10, 0))
    assert d == pytest.approx(0.0)


def test_segment_to_segment_distance_touching_at_endpoint():
    d = segment_to_segment_distance((0, 0), (5, 0), (5, 0), (5, 5))
    assert d == pytest.approx(0.0)


def test_segment_to_segment_distance_collinear_overlap():
    d = segment_to_segment_distance((0, 0), (10, 0), (5, 0), (15, 0))
    assert d == pytest.approx(0.0)


def test_segment_to_segment_distance_parallel():
    # Two parallel horizontal segments, vertical gap of 3.
    d = segment_to_segment_distance((0, 0), (10, 0), (0, 3), (10, 3))
    assert d == pytest.approx(3.0)


def test_segment_to_segment_distance_perpendicular_not_touching():
    # Vertical segment sits 1 unit above the right end of the horizontal one.
    d = segment_to_segment_distance((0, 0), (10, 0), (5, 1), (5, 5))
    assert d == pytest.approx(1.0)


def test_segment_to_segment_distance_disjoint_diagonal():
    # Endpoint of one segment closest to the other segment.
    d = segment_to_segment_distance((0, 0), (1, 0), (2, 0), (2, 1))
    assert d == pytest.approx(1.0)


def test_segment_to_segment_distance_identical_segments():
    d = segment_to_segment_distance((0, 0), (10, 0), (0, 0), (10, 0))
    assert d == pytest.approx(0.0)


def test_segment_to_segment_distance_both_degenerate():
    # Two zero-length segments 5 units apart.
    d = segment_to_segment_distance((0, 0), (0, 0), (3, 4), (3, 4))
    assert d == pytest.approx(5.0)