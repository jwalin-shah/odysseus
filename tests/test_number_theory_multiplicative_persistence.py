"""Tests for ``src.number_theory_multiplicative_persistence``."""

import pytest

from src.number_theory_multiplicative_persistence import (
    number_theory_multiplicative_persistence,
)


# ---------------------------------------------------------------------------
# Edge cases: numbers that are already single digits must have persistence 0.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("value", [0, 1, 2, 5, 9])
def test_single_digit_has_zero_persistence(value):
    assert number_theory_multiplicative_persistence(value) == 0


# ---------------------------------------------------------------------------
# A number containing a zero digit collapses to 0 in a single step.
# ---------------------------------------------------------------------------
def test_ten_collapses_to_zero_in_one_step():
    # 1 * 0 = 0
    assert number_theory_multiplicative_persistence(10) == 1


def test_25_persistence_is_two():
    # 2 * 5 = 10 -> 1 * 0 = 0
    assert number_theory_multiplicative_persistence(25) == 2


# ---------------------------------------------------------------------------
# Well-known persistence values used as a regression table.
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "value, expected",
    [
        (39, 3),       # 39 -> 27 -> 14 -> 4
        (77, 4),       # 77 -> 49 -> 36 -> 18 -> 8
        (679, 5),      # classical example
        (6788, 6),
        (68889, 7),
        (2677889, 8),
        (26888999, 9),
        (999, 4),      # 999 -> 729 -> 126 -> 12 -> 2
    ],
)
def test_known_persistence_values(value, expected):
    assert number_theory_multiplicative_persistence(value) == expected


# ---------------------------------------------------------------------------
# Result must be a non-negative integer regardless of input size.
# ---------------------------------------------------------------------------
def test_result_is_non_negative_integer():
    result = number_theory_multiplicative_persistence(277777788888899)
    assert isinstance(result, int)
    assert result >= 0


# ---------------------------------------------------------------------------
# Input validation: type and sign must be rejected.
# ---------------------------------------------------------------------------
def test_negative_input_raises_value_error():
    with pytest.raises(ValueError):
        number_theory_multiplicative_persistence(-1)


def test_non_integer_input_raises_type_error():
    with pytest.raises(TypeError):
        number_theory_multiplicative_persistence(1.5)  # type: ignore[arg-type]


def test_boolean_input_raises_type_error():
    with pytest.raises(TypeError):
        number_theory_multiplicative_persistence(True)  # type: ignore[arg-type]