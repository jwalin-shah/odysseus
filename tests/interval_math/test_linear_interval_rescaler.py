"""Tests for ``interval_math.linear_interval_rescaler.linear_interval_rescaler``."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the repository root importable regardless of where pytest is invoked.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from interval_math.linear_interval_rescaler import linear_interval_rescaler


# ---------------------------------------------------------------------------
# Happy-path behavior
# ---------------------------------------------------------------------------

def test_endpoints_map_to_target_bounds():
    rescale = linear_interval_rescaler((0.0, 10.0), 0.0, 1.0)
    assert rescale(0.0) == pytest.approx(0.0)
    assert rescale(10.0) == pytest.approx(1.0)


def test_midpoint_is_midpoint_for_identity_source():
    rescale = linear_interval_rescaler((0.0, 100.0), 0.0, 1.0)
    assert rescale(50.0) == pytest.approx(0.5)


def test_midpoint_is_midpoint_for_negative_source():
    rescale = linear_interval_rescaler((-1.0, 1.0), 0.0, 1.0)
    assert rescale(-1.0) == pytest.approx(0.0)
    assert rescale(0.0) == pytest.approx(0.5)
    assert rescale(1.0) == pytest.approx(1.0)


def test_arbitrary_target_range():
    rescale = linear_interval_rescaler((0.0, 5.0), -2.0, 3.0)
    assert rescale(0.0) == pytest.approx(-2.0)
    assert rescale(2.5) == pytest.approx(0.5)
    assert rescale(5.0) == pytest.approx(3.0)


def test_non_zero_input_offset():
    rescale = linear_interval_rescaler((10.0, 20.0), 100.0, 200.0)
    assert rescale(10.0) == pytest.approx(100.0)
    assert rescale(15.0) == pytest.approx(150.0)
    assert rescale(20.0) == pytest.approx(200.0)


def test_inverted_source_interval_is_supported():
    # The transformation is still well-defined when the source interval is
    # written high-to-low: the rescaling simply has a negative scale.
    rescale = linear_interval_rescaler((10.0, 0.0), 0.0, 1.0)
    assert rescale(10.0) == pytest.approx(0.0)
    assert rescale(0.0) == pytest.approx(1.0)
    assert rescale(5.0) == pytest.approx(0.5)


def test_default_target_range_is_unit_interval():
    rescale = linear_interval_rescaler((0.0, 4.0))
    assert rescale(0.0) == pytest.approx(0.0)
    assert rescale(1.0) == pytest.approx(0.25)
    assert rescale(4.0) == pytest.approx(1.0)


def test_list_input_works_like_tuple():
    rescale_tuple = linear_interval_rescaler((0.0, 5.0), 0.0, 1.0)
    rescale_list = linear_interval_rescaler([0.0, 5.0], 0.0, 1.0)
    for x in (0.0, 1.25, 2.5, 3.75, 5.0):
        assert rescale_tuple(x) == pytest.approx(rescale_list(x))


def test_integer_inputs_are_accepted():
    rescale = linear_interval_rescaler((0, 10), 0, 100)
    assert rescale(0) == pytest.approx(0.0)
    assert rescale(5) == pytest.approx(50.0)
    assert rescale(10) == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# Edge cases / error handling
# ---------------------------------------------------------------------------

def test_zero_width_interval_raises():
    with pytest.raises(ValueError):
        linear_interval_rescaler((5.0, 5.0), 0.0, 1.0)


def test_invalid_interval_length_raises():
    with pytest.raises(ValueError):
        linear_interval_rescaler((0.0, 1.0, 2.0), 0.0, 1.0)
    with pytest.raises(ValueError):
        linear_interval_rescaler((0.0,), 0.0, 1.0)
    with pytest.raises(ValueError):
        linear_interval_rescaler([], 0.0, 1.0)


def test_non_sequence_interval_raises():
    with pytest.raises(ValueError):
        linear_interval_rescaler(5.0, 0.0, 1.0)


def test_non_numeric_interval_raises():
    with pytest.raises(ValueError):
        linear_interval_rescaler(("a", "b"), 0.0, 1.0)
    with pytest.raises(ValueError):
        linear_interval_rescaler((0.0, "b"), 0.0, 1.0)


def test_non_numeric_target_bounds_raise():
    with pytest.raises(ValueError):
        linear_interval_rescaler((0.0, 1.0), "0", 1.0)
    with pytest.raises(ValueError):
        linear_interval_rescaler((0.0, 1.0), 0.0, None)


def test_rescale_non_numeric_input_raises_type_error():
    rescale = linear_interval_rescaler((0.0, 1.0), 0.0, 1.0)
    with pytest.raises(TypeError):
        rescale("0.5")
    with pytest.raises(TypeError):
        rescale(None)


def test_nan_interval_bound_raises():
    nan = float("nan")
    with pytest.raises(ValueError):
        linear_interval_rescaler((nan, 1.0), 0.0, 1.0)
    with pytest.raises(ValueError):
        linear_interval_rescaler((0.0, nan), 0.0, 1.0)