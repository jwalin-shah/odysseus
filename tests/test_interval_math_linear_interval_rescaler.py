"""Tests for ``interval_math_linear_interval_rescaler``."""

import math

import pytest

from src.interval_math_linear_interval_rescaler import (
    interval_math_linear_interval_rescaler,
)


def test_midpoint_maps_to_midpoint():
    # 0.5 is the midpoint of [0, 1]; the midpoint of [0, 100] is 50.
    assert interval_math_linear_interval_rescaler(0.5, 0, 1, 0, 100) == 50.0


def test_lower_bound_maps_to_lower_bound():
    assert interval_math_linear_interval_rescaler(0, 0, 10, 0, 100) == 0.0


def test_upper_bound_maps_to_upper_bound():
    assert interval_math_linear_interval_rescaler(10, 0, 10, 0, 100) == 100.0


def test_negative_source_interval():
    # -1 is one quarter of the way from -2 to 2, so it maps to 2.5 in [0, 10].
    result = interval_math_linear_interval_rescaler(-1, -2, 2, 0, 10)
    assert result == pytest.approx(2.5)


def test_inverted_target_interval():
    # When the target interval is reversed, a high source value maps low.
    result = interval_math_linear_interval_rescaler(0.75, 0, 1, 1, 0)
    assert result == pytest.approx(0.25)


def test_zero_width_source_returns_target_midpoint():
    # Any value in a degenerate source interval maps to the target midpoint.
    result = interval_math_linear_interval_rescaler(5, 7, 7, 0, 10)
    assert result == pytest.approx(5.0)


def test_zero_width_source_and_zero_width_target():
    # If both intervals are degenerate, the only sensible value is that point.
    result = interval_math_linear_interval_rescaler(3, 7, 7, 4, 4)
    assert result == pytest.approx(4.0)


def test_extrapolation_above_source_upper_bound():
    # Values above src_hi are extrapolated linearly.
    result = interval_math_linear_interval_rescaler(15, 0, 10, 0, 100)
    assert result == pytest.approx(150.0)


def test_extrapolation_below_source_lower_bound():
    result = interval_math_linear_interval_rescaler(-5, 0, 10, 0, 100)
    assert result == pytest.approx(-50.0)


def test_accepts_integer_inputs():
    # Integer inputs should be accepted and produce a float result.
    result = interval_math_linear_interval_rescaler(2, 0, 4, 0, 8)
    assert result == pytest.approx(4.0)
    assert isinstance(result, float)


def test_rescaling_is_invertible():
    # Mapping [0, 1] -> [10, 20] and then back should recover the original.
    forward = interval_math_linear_interval_rescaler(0.3, 0, 1, 10, 20)
    backward = interval_math_linear_interval_rescaler(forward, 10, 20, 0, 1)
    assert backward == pytest.approx(0.3)


def test_non_numeric_value_raises_type_error():
    with pytest.raises(TypeError):
        interval_math_linear_interval_rescaler("0.5", 0, 1, 0, 100)


def test_boolean_value_is_rejected():
    # ``True`` / ``False`` are not real numbers for our purposes.
    with pytest.raises(TypeError):
        interval_math_linear_interval_rescaler(True, 0, 1, 0, 100)


def test_unit_interval_to_arbitrary_interval():
    # General sanity check with a non-trivial target.
    value = 0.25
    expected = -5 + 0.25 * (15 - (-5))  # == 0
    result = interval_math_linear_interval_rescaler(value, 0, 1, -5, 15)
    assert math.isclose(result, expected)