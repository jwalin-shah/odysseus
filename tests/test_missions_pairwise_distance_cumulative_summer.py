"""Tests for ``missions_pairwise_distance_cumulative_summer``."""

from __future__ import annotations

import math

import pytest

from src.missions_pairwise_distance_cumulative_summer import (
    missions_pairwise_distance_cumulative_summer,
)


class _Mission:
    """Lightweight stand-in for a domain-specific mission object."""

    def __init__(self, x, y):
        self.x = x
        self.y = y


# ---------------------------------------------------------------------------
# Degenerate inputs
# ---------------------------------------------------------------------------


def test_none_input_returns_zero():
    assert missions_pairwise_distance_cumulative_summer(None) == 0.0


def test_empty_list_returns_zero():
    assert missions_pairwise_distance_cumulative_summer([]) == 0.0


def test_empty_tuple_returns_zero():
    assert missions_pairwise_distance_cumulative_summer(()) == 0.0


def test_single_mission_returns_zero():
    assert missions_pairwise_distance_cumulative_summer([(5.0, -7.0)]) == 0.0


def test_coincident_missions_return_zero():
    # Two missions on the exact same coordinate pair -> no distance.
    result = missions_pairwise_distance_cumulative_summer(
        [(2.5, -1.0), (2.5, -1.0)]
    )
    assert result == 0.0


# ---------------------------------------------------------------------------
# Basic geometry
# ---------------------------------------------------------------------------


def test_two_missions_3_4_5_triangle():
    # (0,0) to (3,4) has length exactly 5.
    result = missions_pairwise_distance_cumulative_summer([(0, 0), (3, 4)])
    assert math.isclose(result, 5.0)


def test_two_unit_missions():
    result = missions_pairwise_distance_cumulative_summer([(0, 0), (1, 0)])
    assert math.isclose(result, 1.0)


def test_three_collinear_missions_sum_of_segments():
    # Points on the x-axis: (0,0), (1,0), (3,0).
    # Pairwise distances: 1, 3, 2  ->  total 6.
    result = missions_pairwise_distance_cumulative_summer(
        [(0, 0), (1, 0), (3, 0)]
    )
    assert math.isclose(result, 6.0)


def test_four_missions_unit_square():
    # Square vertices: (0,0), (1,0), (1,1), (0,1).
    # 4 sides of length 1 + 2 diagonals of sqrt(2) = 4 + 2*sqrt(2).
    result = missions_pairwise_distance_cumulative_summer(
        [(0, 0), (1, 0), (1, 1), (0, 1)]
    )
    expected = 4.0 + 2.0 * math.sqrt(2)
    assert math.isclose(result, expected)


def test_equilateral_triangle_side_one():
    p1 = (0.0, 0.0)
    p2 = (1.0, 0.0)
    p3 = (0.5, math.sqrt(3) / 2)
    result = missions_pairwise_distance_cumulative_summer([p1, p2, p3])
    # Three sides of length 1.
    assert math.isclose(result, 3.0, abs_tol=1e-12)


# ---------------------------------------------------------------------------
# Supported coordinate encodings
# ---------------------------------------------------------------------------


def test_dict_encoded_missions():
    result = missions_pairwise_distance_cumulative_summer(
        [{"x": 0, "y": 0}, {"x": 3, "y": 4}]
    )
    assert math.isclose(result, 5.0)


def test_object_with_xy_attributes():
    result = missions_pairwise_distance_cumulative_summer(
        [_Mission(0, 0), _Mission(3, 4)]
    )
    assert math.isclose(result, 5.0)


def test_list_encoding_inside():
    # Plain Python lists are accepted in place of tuples.
    result = missions_pairwise_distance_cumulative_summer([[0, 0], [3, 4]])
    assert math.isclose(result, 5.0)


def test_mixed_input_encodings():
    result = missions_pairwise_distance_cumulative_summer(
        [(0, 0), {"x": 1, "y": 0}, _Mission(3, 0)]
    )
    # (0,0)-(1,0)=1, (0,0)-(3,0)=3, (1,0)-(3,0)=2  ->  total 6
    assert math.isclose(result, 6.0)


# ---------------------------------------------------------------------------
# Iterator / generator inputs
# ---------------------------------------------------------------------------


def test_accepts_plain_iterator():
    result = missions_pairwise_distance_cumulative_summer(
        iter([(0, 0), (3, 4), (6, 8)])
    )
    # 5 + 5 + 10  (diagonal from (3,4) to (6,8) is also a 3-4-5 right triangle)
    assert math.isclose(result, 20.0)


def test_accepts_generator_expression():
    result = missions_pairwise_distance_cumulative_summer(
        (pt for pt in [(0, 0), (3, 4)])
    )
    assert math.isclose(result, 5.0)


# ---------------------------------------------------------------------------
# Numerical / algebraic properties
# ---------------------------------------------------------------------------


def test_order_invariance():
    a = missions_pairwise_distance_cumulative_summer(
        [(0, 0), (1, 0), (0, 1), (1, 1)]
    )
    b = missions_pairwise_distance_cumulative_summer(
        [(1, 1), (0, 1), (1, 0), (0, 0)]
    )
    c = missions_pairwise_distance_cumulative_summer(
        [(0, 1), (1, 1), (0, 0), (1, 0)]
    )
    assert math.isclose(a, b)
    assert math.isclose(b, c)
    assert a > 0.0


def test_result_is_non_negative():
    pts = [(-3, -4), (1, 2), (5, -7), (0, 0)]
    assert missions_pairwise_distance_cumulative_summer(pts) >= 0.0


def test_negative_coordinates():
    # (-1,-1) to (2,3): dx=3, dy=4  ->  distance 5
    result = missions_pairwise_distance_cumulative_summer(
        [(-1, -1), (2, 3)]
    )
    assert math.isclose(result, 5.0)


def test_floating_point_coordinates():
    result = missions_pairwise_distance_cumulative_summer(
        [(0.1, 0.2), (0.4, 0.5)]
    )
    expected = math.hypot(0.3, 0.3)
    assert math.isclose(result, expected, rel_tol=1e-12)


def test_pair_count_matches_combination_formula():
    # 5 points -> C(5,2) = 10 pairs.  Use a regular pentagon to confirm we
    # are not double counting or skipping any pair.
    import math as _m

    pts = [
        (_m.cos(2 * _m.pi * k / 5), _m.sin(2 * _m.pi * k / 5))
        for k in range(5)
    ]
    # Side length of a unit regular pentagon is 2*sin(pi/5).
    side = 2 * _m.sin(_m.pi / 5)
    # There are 5 sides and 5 diagonals, but with n=5 the 5 diagonals all have
    # the same length: 2*sin(2*pi/5).  Total = 5*side + 5*diag.
    diag = 2 * _m.sin(2 * _m.pi / 5)
    expected = 5 * side + 5 * diag
    result = missions_pairwise_distance_cumulative_summer(pts)
    assert math.isclose(result, expected, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_unsupported_mission_type_raises_type_error():
    with pytest.raises(TypeError):
        missions_pairwise_distance_cumulative_summer(["not a mission"])


def test_dict_missing_key_raises_type_error():
    with pytest.raises(TypeError):
        missions_pairwise_distance_cumulative_summer(
            [{"x": 0}, {"x": 1, "y": 0}]
        )


def test_non_numeric_coordinate_raises_type_error():
    with pytest.raises(TypeError):
        missions_pairwise_distance_cumulative_summer(
            [(0, 0), ("a", "b")]
        )