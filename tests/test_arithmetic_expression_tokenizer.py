"""Tests for :mod:`arithmetic_expression_tokenizer`."""

import os
import sys

# Make the project root importable so ``import arithmetic_expression_tokenizer``
# works regardless of where pytest is invoked from.
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

import pytest

from arithmetic_expression_tokenizer import arithmetic_expression_tokenizer


# ---------------------------------------------------------------------------
# Basic behaviour
# ---------------------------------------------------------------------------

def test_empty_string_returns_empty_list():
    assert arithmetic_expression_tokenizer("") == []


def test_whitespace_only_string_returns_empty_list():
    assert arithmetic_expression_tokenizer("   \t\n  ") == []


def test_single_integer():
    assert arithmetic_expression_tokenizer("42") == [("NUMBER", "42")]


def test_single_zero():
    assert arithmetic_expression_tokenizer("0") == [("NUMBER", "0")]


def test_decimal_number():
    assert arithmetic_expression_tokenizer("3.14") == [("NUMBER", "3.14")]


def test_number_starting_with_dot():
    assert arithmetic_expression_tokenizer(".5") == [("NUMBER", ".5")]


def test_number_ending_with_dot_has_digit():
    # ``"5."`` contains at least one digit so it is accepted.
    assert arithmetic_expression_tokenizer("5.") == [("NUMBER", "5.")]


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("op", ["+", "-", "*", "/"])
def test_basic_binary_operators(op):
    expr = f"3{op}4"
    expected = [
        ("NUMBER", "3"),
        ("OPERATOR", op),
        ("NUMBER", "4"),
    ]
    assert arithmetic_expression_tokenizer(expr) == expected


def test_two_char_operator_power():
    assert arithmetic_expression_tokenizer("2**3") == [
        ("NUMBER", "2"),
        ("OPERATOR", "**"),
        ("NUMBER", "3"),
    ]


def test_two_char_operator_floor_div():
    assert arithmetic_expression_tokenizer("10//3") == [
        ("NUMBER", "10"),
        ("OPERATOR", "//"),
        ("NUMBER", "3"),
    ]


# ---------------------------------------------------------------------------
# Whitespace handling
# ---------------------------------------------------------------------------

def test_whitespace_is_skipped():
    assert arithmetic_expression_tokenizer("  3   +   4  ") == [
        ("NUMBER", "3"),
        ("OPERATOR", "+"),
        ("NUMBER", "4"),
    ]


def test_no_whitespace_between_tokens():
    assert arithmetic_expression_tokenizer("3+4") == [
        ("NUMBER", "3"),
        ("OPERATOR", "+"),
        ("NUMBER", "4"),
    ]


# ---------------------------------------------------------------------------
# Parentheses and complex expressions
# ---------------------------------------------------------------------------

def test_parentheses():
    assert arithmetic_expression_tokenizer("(1+2)") == [
        ("LPAREN", "("),
        ("NUMBER", "1"),
        ("OPERATOR", "+"),
        ("NUMBER", "2"),
        ("RPAREN", ")"),
    ]


def test_complex_expression_with_decimals():
    expr = "(3.5 + 4) * 2 - 1"
    assert arithmetic_expression_tokenizer(expr) == [
        ("LPAREN", "("),
        ("NUMBER", "3.5"),
        ("OPERATOR", "+"),
        ("NUMBER", "4"),
        ("RPAREN", ")"),
        ("OPERATOR", "*"),
        ("NUMBER", "2"),
        ("OPERATOR", "-"),
        ("NUMBER", "1"),
    ]


def test_nested_parentheses():
    assert arithmetic_expression_tokenizer("((1+2)*(3-4))") == [
        ("LPAREN", "("),
        ("LPAREN", "("),
        ("NUMBER", "1"),
        ("OPERATOR", "+"),
        ("NUMBER", "2"),
        ("RPAREN", ")"),
        ("OPERATOR", "*"),
        ("LPAREN", "("),
        ("NUMBER", "3"),
        ("OPERATOR", "-"),
        ("NUMBER", "4"),
        ("RPAREN", ")"),
        ("RPAREN", ")"),
    ]


def test_full_expression_realistic():
    # ``(1.5 + 2.5) * 3 / 2 ** 2`` should be tokenized into a meaningful
    # sequence.  We assert against the full expected token list.
    assert arithmetic_expression_tokenizer("(1.5+2.5)*3/2**2") == [
        ("LPAREN", "("),
        ("NUMBER", "1.5"),
        ("OPERATOR", "+"),
        ("NUMBER", "2.5"),
        ("RPAREN", ")"),
        ("OPERATOR", "*"),
        ("NUMBER", "3"),
        ("OPERATOR", "/"),
        ("NUMBER", "2"),
        ("OPERATOR", "**"),
        ("NUMBER", "2"),
    ]


# ---------------------------------------------------------------------------
# Unary / leading sign behaviour
# ---------------------------------------------------------------------------

def test_leading_minus_is_emitted_as_operator():
    # The tokenizer does not distinguish unary vs binary minus; the
    # parser is responsible for that.  We just verify that the minus
    # is emitted as a token.
    assert arithmetic_expression_tokenizer("-5") == [
        ("OPERATOR", "-"),
        ("NUMBER", "5"),
    ]


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_non_string_input_raises_type_error():
    with pytest.raises(TypeError):
        arithmetic_expression_tokenizer(123)
    with pytest.raises(TypeError):
        arithmetic_expression_tokenizer(None)
    with pytest.raises(TypeError):
        arithmetic_expression_tokenizer([1, 2, 3])


def test_unknown_character_raises_value_error():
    with pytest.raises(ValueError):
        arithmetic_expression_tokenizer("3 & 4")
    with pytest.raises(ValueError):
        arithmetic_expression_tokenizer("foo")
    with pytest.raises(ValueError):
        arithmetic_expression_tokenizer("3$4")


def test_lone_dot_is_invalid_number():
    with pytest.raises(ValueError):
        arithmetic_expression_tokenizer(".")


def test_dot_followed_by_operator_is_invalid_number():
    # ``".+5"`` starts a number with ``.`` but never sees a digit.
    with pytest.raises(ValueError):
        arithmetic_expression_tokenizer(".+5")