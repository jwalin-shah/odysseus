"""Tests for ``perpendicular_foot``."""

import math

import pytest

from perpendicular_foot import perpendicular_foot


def _close(a, b, tol=1e-9):
    """Compare two floats with a small absolute tolerance."""
    return math.isclose(a, b, abs_tol=tol)


def test_point_on_line_returns_itself():
    """A point already on the line should be its own perpendicular foot."""
    assert perpendicular_foot((1.0, 0.5), (0.0, 0.0), (2.0, 1.0)) == (1.0, 0.5)


def test_horizontal_line():
    """Dropping a perpendicular from (3, 5) onto the x-axis yields (3, 0)."""
    fx, fy = perpendicular_foot((3.0, 5.0), (0.0, 0.0), (1.0, 0.0))
    assert _close(fx, 3.0)
    assert _close(fy, 0.0)


def test_vertical_line():
    """Dropping a perpendicular from (5, 3) onto the y-axis yields (0, 3)."""
    fx, fy = perpendicular_foot((5.0, 3.0), (0.0, 0.0), (0.0, 1.0))
    assert _close(fx, 0.0)
    assert _close(fy, 3.0)


def test_diagonal_line():
    """Dropping a perpendicular from (2, 0) onto y = x yields (1, 1)."""
    fx, fy = perpendicular_foot((2.0, 0.0), (0.0, 0.0), (1.0, 1.0))
    assert _close(fx, 1.0)
    assert _close(fy, 1.0)


def test_foot_lies_on_line():
    """The returned foot must lie on the (infinite) line through A and B."""
    start = (1.0, 2.0)
    end = (5.0, 8.0)
    point = (3.0, -1.0)
    foot = perpendicular_foot(point, start, end)

    # Cross product of (foot - start) with (end - start) should be zero.
    cross = (foot[0] - start[0]) * (end[1] - start[1]) - \
            (foot[1] - start[1]) * (end[0] - start[0])
    assert _close(cross, 0.0)


def test_segment_pf_perpendicular_to_line():
    """The vector PF must be perpendicular to the line direction."""
    start = (0.0, 0.0)
    end = (3.0, 0.0)
    point = (1.0, 7.0)
    foot = perpendicular_foot(point, start, end)

    px, py = point
    fx, fy = foot
    sx, sy = start
    ex, ey = end

    # Dot product of (foot - point) with (end - start) should be zero.
    dot = (fx - px) * (ex - sx) + (fy - py) * (ey - sy)
    assert _close(dot, 0.0)


def test_degenerate_line_returns_start():
    """If both endpoints coincide, the function returns that single point."""
    assert perpendicular_foot((5.0, 5.0), (3.0, 4.0), (3.0, 4.0)) == (3.0, 4.0)


def test_point_on_negative_diagonal():
    """A point on y = x in the negative quadrant projects onto itself."""
    assert perpendicular_foot((-1.0, -1.0), (-2.0, -2.0), (2.0, 2.0)) == (-1.0, -1.0)


def test_foot_beyond_segment_endpoint():
    """The function operates on the infinite line, not the segment."""
    # P = (5, 5); horizontal segment [0, 1] on x-axis. Foot = (5, 0).
    fx, fy = perpendicular_foot((5.0, 5.0), (0.0, 0.0), (1.0, 0.0))
    assert _close(fx, 5.0)
    assert _close(fy, 0.0)


def test_foot_before_segment_start():
    """The foot can lie 'before' line_start along the line direction."""
    # P = (-3, 2); horizontal line. Foot = (-3, 0).
    fx, fy = perpendicular_foot((-3.0, 2.0), (0.0, 0.0), (1.0, 0.0))
    assert _close(fx, -3.0)
    assert _close(fy, 0.0)


def test_accepts_lists():
    """Inputs may be lists as well as tuples."""
    fx, fy = perpendicular_foot([2.0, 3.0], [0.0, 0.0], [4.0, 0.0])
    assert _close(fx, 2.0)
    assert _close(fy, 0.0)


def test_translated_line():
    """Translating the line translates the foot by the same amount."""
    # Same setup as test_horizontal_line but shifted up by 10.
    fx, fy = perpendicular_foot((3.0, 15.0), (0.0, 10.0), (1.0, 10.0))
    assert _close(fx, 3.0)
    assert _close(fy, 10.0)


def test_arbitrary_angle():
    """Spot-check an arbitrary line and point with a known result."""
    # Line through A=(1, 1) and B=(4, 5); direction d=(3, 4), |d|^2=25.
    # P=(2, 6); w = P - A = (1, 5).
    # t = (1*3 + 5*4) / 25 = (3 + 20) / 25 = 23/25 = 0.92
    # F = (1 + 0.92*3, 1 + 0.92*4) = (1 + 2.76, 1 + 3.68) = (3.76, 4.68)
    fx, fy = perpendicular_foot((2.0, 6.0), (1.0, 1.0), (4.0, 5.0))
    assert _close(fx, 3.76)
    assert _close(fy, 4.68)


def test_integer_inputs_are_coerced():
    """Integer coordinates should work transparently and return floats."""
    foot = perpendicular_foot((3, 5), (0, 0), (1, 0))
    assert isinstance(foot, tuple)
    assert all(isinstance(c, float) for c in foot)
    assert _close(foot[0], 3.0)
    assert _close(foot[1], 0.0)