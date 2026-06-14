"""Tests for point_to_segment_distance in src.geometry_distance.

These tests exercise the function specified in the mission: compute the
shortest Euclidean distance from a 2D point to a finite line segment,
including the degenerate (zero-length) segment case and endpoint cases.
"""

import math

import pytest

from src.geometry_distance import point_to_segment_distance


def test_function_is_importable_and_callable_with_three_positional_args():
    """AC1: the symbol exists and is callable with three positional arguments."""
    # If the import above succeeded, the symbol exists in the module.
    assert callable(point_to_segment_distance)
    # Calling with three positional args must succeed and return a number.
    result = point_to_segment_distance([2, 2], [0, 0], [4, 0])
    assert isinstance(result, (int, float))


@pytest.mark.parametrize(
    "point, segment_start, segment_end, expected",
    [
        # AC2: provided case 1 — perpendicular projection onto interior of segment.
        ([2, 2], [0, 0], [4, 0], 2.0),
        # AC3: provided case 2 — projection falls beyond the segment endpoint.
        ([5, 3], [0, 0], [4, 0], math.sqrt(10)),
        # AC4: provided case 3 — projection falls before the segment startpoint.
        ([-1, 0], [0, 0], [2, 0], 1.0),
        # AC5: point lies exactly on the segment interior — distance is zero.
        ([1, 0], [0, 0], [2, 0], 0.0),
        # AC6: point coincides with a segment endpoint — distance is zero.
        ([0, 0], [0, 0], [2, 0], 0.0),
        # AC7: degenerate (zero-length) segment — distance is point-to-point.
        ([3, 4], [0, 0], [0, 0], 5.0),
        # EC4: perpendicular foot exactly at endpoint (t at boundary).
        ([2, 1], [0, 0], [2, 0], 1.0),
        # EC5: point lies on the extension of the segment, closest point is endpoint.
        ([-1, -1], [-3, 0], [-1, 0], 1.0),
        # Additional symmetric check: point on the segment's other endpoint.
        ([2, 0], [0, 0], [2, 0], 0.0),
    ],
)
def test_point_to_segment_distance_values(point, segment_start, segment_end, expected):
    """AC2-AC7 + edge cases: numerical correctness within 1e-9 tolerance."""
    result = point_to_segment_distance(point, segment_start, segment_end)
    assert result == pytest.approx(expected, abs=1e-9)


def test_all_pytest_cases_collect_and_run():
    """AC8: the test file must be collectable by pytest (sentinel for exit-status 0)."""
    # A trivial assertion that still requires the test file to be valid Python
    # and importable under pytest collection. The parametrized cases above
    # already cover the numerical expectations; this sentinel ensures the
    # module itself is structurally sound so the full pytest run is green
    # once point_to_segment_distance is implemented.
    assert point_to_segment_distance is not None
