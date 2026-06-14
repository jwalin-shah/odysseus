"""Tests for the ``rpn_eval`` function."""

import os
import sys

import pytest

# Make the implementation importable when running ``pytest`` from the
# project root without installing the package.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from rpn_eval import rpn_eval  # noqa: E402


# ---------------------------------------------------------------------------
# Basic arithmetic with string input
# ---------------------------------------------------------------------------


def test_simple_addition_string():
    assert rpn_eval("3 4 +") == 7


def test_simple_subtraction_string():
    assert rpn_eval("10 3 -") == 7


def test_simple_multiplication_string():
    assert rpn_eval("4 5 *") == 20


def test_simple_division_string():
    assert rpn_eval("20 4 /") == 5.0


def test_power_operator_string():
    assert rpn_eval("2 3 **") == 8


# ---------------------------------------------------------------------------
# Complex / nested expressions
# ---------------------------------------------------------------------------


def test_classic_rpn_example():
    # 5 + (1 + 2) * 4 = 5 + 12 = 17
    assert rpn_eval("5 1 2 + 4 * +") == 17


def test_chained_multiplication_and_division():
    # (6 / 2) * (1 + 2) = 3 * 3 = 9
    assert rpn_eval("6 2 / 1 2 + *") == 9.0


def test_deeply_nested_expression():
    # ((15 / (7 - (1 + 1))) * (-3 + (2 + 1))) = (15 / 5) * 0 = 0
    assert rpn_eval("15 7 1 1 + - / -3 2 1 + + *") == 0.0


def test_extra_whitespace_in_string_is_ignored():
    assert rpn_eval("  3   4   +  ") == 7


# ---------------------------------------------------------------------------
# Alternative input shapes
# ---------------------------------------------------------------------------


def test_list_input_with_string_tokens():
    assert rpn_eval(["3", "4", "+"]) == 7


def test_list_input_with_numeric_tokens():
    assert rpn_eval([3, 4, "+"]) == 7


def test_tuple_input():
    assert rpn_eval((3, 4, "+")) == 7


def test_mixed_list_tokens():
    assert rpn_eval([3, "4", "+"]) == 7


def test_single_number_string():
    assert rpn_eval("42") == 42


def test_single_number_list():
    assert rpn_eval([42]) == 42


# ---------------------------------------------------------------------------
# Numeric edge cases
# ---------------------------------------------------------------------------


def test_negative_result():
    assert rpn_eval("3 10 -") == -7


def test_negative_input_numbers():
    assert rpn_eval("-3 5 +") == 2


def test_float_numbers():
    assert rpn_eval("2.5 4 *") == 10.0


def test_integer_inputs_preserve_int_for_addition():
    result = rpn_eval("2 3 +")
    assert result == 5
    assert isinstance(result, int)


def test_division_always_returns_float():
    result = rpn_eval("4 2 /")
    assert result == 2.0
    assert isinstance(result, float)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_empty_string_raises_value_error():
    with pytest.raises(ValueError):
        rpn_eval("")


def test_whitespace_only_string_raises_value_error():
    with pytest.raises(ValueError):
        rpn_eval("   \t  ")


def test_empty_list_raises_value_error():
    with pytest.raises(ValueError):
        rpn_eval([])


def test_too_few_operands_raises_value_error():
    with pytest.raises(ValueError):
        rpn_eval("3 +")


def test_too_many_operands_raises_value_error():
    with pytest.raises(ValueError):
        rpn_eval("3 4 + 5")


def test_division_by_zero_raises_zero_division_error():
    with pytest.raises(ZeroDivisionError):
        rpn_eval("5 0 /")


def test_unknown_operator_raises_value_error():
    with pytest.raises(ValueError):
        rpn_eval("3 4 %")


def test_non_numeric_token_raises_value_error():
    with pytest.raises(ValueError):
        rpn_eval("3 foo +")


def test_invalid_top_level_type_raises_type_error():
    with pytest.raises(TypeError):
        rpn_eval(42)


def test_invalid_top_level_type_none_raises_type_error():
    with pytest.raises(TypeError):
        rpn_eval(None)


def test_invalid_token_type_in_list_raises_type_error():
    with pytest.raises(TypeError):
        rpn_eval([3, None, "+"])


# ---------------------------------------------------------------------------
# Realistic / sanity-check expressions
# ---------------------------------------------------------------------------


def test_compute_polynomial():
    # 3 4 5 * -7 + -> 3 + ((4 * 5) - 7) = 3 + 13 = 16
    assert rpn_eval("3 4 5 * 7 - +") == 16


def test_long_expression_with_all_operators():
    # 10 2 8 * + 3 - 6 / -> ((10 + (2*8)) - 3) / 6 = (26 - 3) / 6 = 23/6
    result = rpn_eval("10 2 8 * + 3 - 6 /")
    assert result == pytest.approx(23 / 6)