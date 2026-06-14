"""Tests for :func:`stats_mad_around_mean`."""

from __future__ import annotations

import math
import os
import sys

import pytest

# Make the ``src`` directory importable when tests are run directly
# from the project root with ``pytest`` without any extra configuration.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from stats_mad_around_mean import stats_mad_around_mean  # noqa: E402


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_sequence_returns_zero():
    """An empty input is a valid degenerate case and should yield 0.0."""
    assert stats_mad_around_mean([]) == 0.0


def test_single_element_returns_zero():
    """A single point has zero deviation from its own mean."""
    assert stats_mad_around_mean([42]) == 0.0
    assert stats_mad_around_mean([-7.5]) == 0.0
    assert stats_mad_around_mean([0]) == 0.0


def test_all_identical_values_returns_zero():
    """Identical values produce no deviation."""
    assert stats_mad_around_mean([3, 3, 3, 3, 3]) == 0.0
    assert stats_mad_around_mean([1.25, 1.25, 1.25]) == 0.0


# ---------------------------------------------------------------------------
# Hand-computed correctness checks
# ---------------------------------------------------------------------------


def test_symmetric_range_around_zero():
    """For [-2, -1, 0, 1, 2] the mean is 0 and MAD is 6/5 = 1.2."""
    assert math.isclose(
        stats_mad_around_mean([-2, -1, 0, 1, 2]), 1.2, rel_tol=1e-12
    )


def test_simple_ascending_sequence():
    """For [1, 2, 3, 4, 5] the mean is 3 and MAD is 6/5 = 1.2."""
    assert math.isclose(
        stats_mad_around_mean([1, 2, 3, 4, 5]), 1.2, rel_tol=1e-12
    )


def test_two_value_pair():
    """For [10, 20] the mean is 15 and MAD is 5."""
    assert math.isclose(stats_mad_around_mean([10, 20]), 5.0, rel_tol=1e-12)


def test_floats_three_values():
    """For [1.5, 2.5, 3.5] the mean is 2.5 and MAD is 2/3."""
    assert math.isclose(
        stats_mad_around_mean([1.5, 2.5, 3.5]), 2.0 / 3.0, rel_tol=1e-12
    )


def test_constant_translation_does_not_change_mad():
    """Adding the same constant to every value leaves MAD unchanged."""
    base = stats_mad_around_mean([1, 4, 7, 9, 12])
    shifted = stats_mad_around_mean([x + 100 for x in [1, 4, 7, 9, 12]])
    assert math.isclose(base, shifted, rel_tol=1e-12)


def test_linear_scaling_scales_mad():
    """Multiplying every value by a constant scales MAD by that constant."""
    base = stats_mad_around_mean([2, 5, 7, 11])
    scaled = stats_mad_around_mean([x * 3.5 for x in [2, 5, 7, 11]])
    assert math.isclose(scaled, base * 3.5, rel_tol=1e-12)


# ---------------------------------------------------------------------------
# Output type contract
# ---------------------------------------------------------------------------


def test_returns_python_float():
    """The result must always be a built-in ``float``."""
    assert isinstance(stats_mad_around_mean([1, 2, 3]), float)
    assert isinstance(stats_mad_around_mean([1]), float)
    assert isinstance(stats_mad_around_mean([]), float)


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_non_iterable_raises_type_error():
    """Passing a non-iterable value should raise ``TypeError``."""
    with pytest.raises(TypeError):
        stats_mad_around_mean(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        stats_mad_around_mean(None)  # type: ignore[arg-type]


def test_string_raises_type_error():
    """A bare string is iterable of non-numeric chars; reject it."""
    with pytest.raises(TypeError):
        stats_mad_around_mean("123")  # type: ignore[arg-type]


def test_non_numeric_element_raises_type_error():
    """An element that is not a real number should be rejected."""
    with pytest.raises(TypeError):
        stats_mad_around_mean([1, 2, "three", 4])


def test_mixed_int_and_float_inputs():
    """Mixing ints and floats is allowed and should produce a float result."""
    result = stats_mad_around_mean([0, 1, 2, 3])
    assert math.isclose(result, 1.0, rel_tol=1e-12)
    assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Iterables other than lists should also work
# ---------------------------------------------------------------------------


def test_accepts_tuple_input():
    """Tuples (and other iterables) are valid input as well."""
    assert math.isclose(
        stats_mad_around_mean((1, 2, 3, 4, 5)), 1.2, rel_tol=1e-12
    )


def test_accepts_generator_input():
    """A one-shot generator must work and produce the correct value."""
    gen = (x for x in [2, 4, 6, 8])
    # mean = 5, deviations = 3, 1, 1, 3, sum = 8, MAD = 2
    assert math.isclose(stats_mad_around_mean(gen), 2.0, rel_tol=1e-12)