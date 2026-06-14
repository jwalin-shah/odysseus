"""Tests for ``postfix_evaluator``."""
import os
import sys

import pytest

# Make the project root importable regardless of where pytest is invoked.
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from postfix_evaluator import postfix_evaluator  # noqa: E402


# ---------------------------------------------------------------------------
# Basic single-operator expressions
# ---------------------------------------------------------------------------


def test_addition():
    assert postfix_evaluator("3 4 +") == 7


def test_subtraction():
    assert postfix_evaluator("10 3 -") == 7


def test_multiplication():
    assert postfix_evaluator("3 4 *") == 12


def test_division():
    assert postfix_evaluator("12 4 /") == 3


def test_integer_division():
    assert postfix_evaluator("7 2 //") == 3


def test_modulo():
    assert postfix_evaluator("7 3 %") == 1


def test_power():
    assert postfix_evaluator("2 3 **") == 8


# ---------------------------------------------------------------------------
# Multi-operator / nested expressions
# ---------------------------------------------------------------------------


def test_complex_expression():
    # (3 + 4) * 2 - 1 = 14 - 1 = 13
    assert postfix_evaluator("3 4 + 2 * 1 -") == 13


def test_nested_expression():
    # ((15 / 3) + (4 * 2)) - 1 = (5 + 8) - 1 = 12
    assert postfix_evaluator("15 3 / 4 2 * + 1 -") == 12


def test_left_associativity_via_postfix():
    # 10 - 3 - 2  =>  (10 - 3) - 2 = 5
    assert postfix_evaluator("10 3 - 2 -") == 5


# ---------------------------------------------------------------------------
# Number formats
# ---------------------------------------------------------------------------


def test_single_integer():
    assert postfix_evaluator("42") == 42


def test_single_negative_integer():
    assert postfix_evaluator("-7") == -7


def test_negative_operands_in_expression():
    assert postfix_evaluator("-5 3 +") == -2


def test_floats():
    result = postfix_evaluator("1.5 2.5 +")
    assert result == 4.0
    assert isinstance(result, float)


def test_scientific_notation():
    assert postfix_evaluator("1e2 50 -") == 50.0


# ---------------------------------------------------------------------------
# Error / edge cases
# ---------------------------------------------------------------------------


def test_division_by_zero_integer():
    with pytest.raises(ZeroDivisionError):
        postfix_evaluator("5 0 /")


def test_division_by_zero_float():
    with pytest.raises(ZeroDivisionError):
        postfix_evaluator("5.0 0.0 /")


def test_modulo_by_zero():
    with pytest.raises(ZeroDivisionError):
        postfix_evaluator("5 0 %")


def test_invalid_expression_missing_operand():
    with pytest.raises(ValueError):
        postfix_evaluator("3 +")


def test_invalid_expression_too_many_operands():
    with pytest.raises(ValueError):
        postfix_evaluator("3 4 5 +")


def test_unknown_operator():
    with pytest.raises(ValueError):
        postfix_evaluator("3 4 &")


def test_unknown_token():
    with pytest.raises(ValueError):
        postfix_evaluator("3 abc +")


def test_non_string_input_int():
    with pytest.raises(TypeError):
        postfix_evaluator(123)


def test_non_string_input_list():
    with pytest.raises(TypeError):
        postfix_evaluator([3, 4, "+"])


def test_non_string_input_none():
    with pytest.raises(TypeError):
        postfix_evaluator(None)


def test_empty_expression():
    with pytest.raises(ValueError):
        postfix_evaluator("")


def test_whitespace_only_expression():
    with pytest.raises(ValueError):
        postfix_evaluator("   \t  ")