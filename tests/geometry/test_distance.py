"""Tests for geometry.distance."""

import math

import pytest

from geometry.distance import euclidean, point_to_segment


class TestEuclidean:
    def test_basic_2d_3_4_5_triangle(self):
        assert euclidean((0, 0), (3, 4)) == pytest.approx(5.0)

    def test_same_point_is_zero(self):
        assert euclidean((1, 2, 3), (1, 2, 3)) == pytest.approx(0.0)

    def test_3d_distance(self):
        # (1,2,3) to (4,6,3) -> dx=3, dy=4, dz=0 -> 5
        assert euclidean((1, 2, 3), (4, 6, 3)) == pytest.approx(5.0)

    def test_negative_coordinates(self):
        # (-1,-1) to (2,3) -> dx=3, dy=4 -> 5
        assert euclidean((-1, -1), (2, 3)) == pytest.approx(5.0)

    def test_symmetry(self):
        assert euclidean((0, 0), (1, 2)) == pytest.approx(euclidean((1, 2), (0, 0)))

    def test_unit_distance(self):
        assert euclidean((0, 0), (1, 0)) == pytest.approx(1.0)
        assert euclidean((0, 0, 0), (0, 1, 0)) == pytest.approx(1.0)

    @pytest.mark.parametrize(
        "p1,p2",
        [
            ((0, 0), (1, 2, 3)),
            ((1, 2), (1, 2, 3)),
            ((0, 0, 0), (1, 2)),
        ],
    )
    def test_dimension_mismatch_raises(self, p1, p2):
        with pytest.raises(ValueError):
            euclidean(p1, p2)


class TestPointToSegment:
    def test_perpendicular_projection(self):
        # Perpendicular from (0, 2) onto segment (-1, 0) - (1, 0)
        # lands at (0, 0), distance 2.
        assert point_to_segment((0, 2), (-1, 0), (1, 0)) == pytest.approx(2.0)

    def test_point_coincides_with_endpoint_a(self):
        assert point_to_segment((0, 0), (0, 0), (3, 4)) == pytest.approx(0.0)

    def test_point_coincides_with_endpoint_b(self):
        assert point_to_segment((3, 4), (0, 0), (3, 4)) == pytest.approx(0.0)

    def test_point_on_segment(self):
        # Point (2, 0) lies on segment (0, 0) - (4, 0).
        assert point_to_segment((2, 0), (0, 0), (4, 0)) == pytest.approx(0.0)

    def test_point_beyond_endpoint_a(self):
        # Segment (1, 0) - (3, 0), point (0, 0): closest is (1, 0), dist 1.
        assert point_to_segment((0, 0), (1, 0), (3, 0)) == pytest.approx(1.0)

    def test_point_beyond_endpoint_b(self):
        # Segment (1, 0) - (3, 0), point (4, 0): closest is (3, 0), dist 1.
        assert point_to_segment((4, 0), (1, 0), (3, 0)) == pytest.approx(1.0)

    def test_degenerate_segment(self):
        # Segment collapses to (1, 1); distance from (3, 4) to (1, 1)
        # is sqrt(2^2 + 3^2) = sqrt(13).
        assert point_to_segment((3, 4), (1, 1), (1, 1)) == pytest.approx(
            math.sqrt(13)
        )

    def test_3d_segment_perpendicular(self):
        # Segment along x-axis from (0,0,0) to (2,0,0); point (1,1,1)
        # projects to (1,0,0), distance sqrt(2).
        assert point_to_segment((1, 1, 1), (0, 0, 0), (2, 0, 0)) == pytest.approx(
            math.sqrt(2)
        )

    def test_3d_segment_beyond_endpoint(self):
        # Segment (0,0,0) - (1,1,1); point (3,3,3) is past b, closest is b.
        assert point_to_segment((3, 3, 3), (0, 0, 0), (1, 1, 1)) == pytest.approx(
            math.sqrt(12)
        )

    @pytest.mark.parametrize(
        "p,a,b",
        [
            ((0, 0), (0, 0, 0), (1, 2, 3)),
            ((1, 2, 3), (0, 0), (1, 2)),
        ],
    )
    def test_dimension_mismatch_raises(self, p, a, b):
        with pytest.raises(ValueError):
            point_to_segment(p, a, b)