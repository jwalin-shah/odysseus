"""Tests for ``missions.logical_expression_tokenizer``."""

from __future__ import annotations

import os
import sys

import pytest

# Make the project root importable so ``from missions import ...`` works
# when this file is executed directly (e.g. ``pytest`` from the repo root).
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from missions.logical_expression_tokenizer import (  # noqa: E402
    Token,
    TokenType,
    logical_expression_tokenizer,
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _types(tokens):
    return [t.type for t in tokens]


def _values(tokens):
    return [t.value for t in tokens]


# ---------------------------------------------------------------------------
# basic single-token cases
# ---------------------------------------------------------------------------


def test_single_variable():
    tokens = logical_expression_tokenizer("x")
    assert _types(tokens) == [TokenType.VARIABLE, TokenType.EOF]
    assert tokens[0].value == "x"
    assert tokens[0].position == 0


def test_empty_string_yields_only_eof():
    tokens = logical_expression_tokenizer("")
    assert _types(tokens) == [TokenType.EOF]
    assert tokens[0].position == 0


def test_whitespace_only_yields_only_eof():
    tokens = logical_expression_tokenizer("   \t\n  ")
    assert _types(tokens) == [TokenType.EOF]


# ---------------------------------------------------------------------------
# keyword logical operators
# ---------------------------------------------------------------------------


def test_and_keyword():
    tokens = logical_expression_tokenizer("a and b")
    assert _types(tokens) == [
        TokenType.VARIABLE, TokenType.AND, TokenType.VARIABLE, TokenType.EOF
    ]
    assert _values(tokens) == ["a", "and", "b", ""]


def test_or_keyword():
    tokens = logical_expression_tokenizer("x or y")
    assert _types(tokens) == [
        TokenType.VARIABLE, TokenType.OR, TokenType.VARIABLE, TokenType.EOF
    ]


def test_not_keyword():
    tokens = logical_expression_tokenizer("not a")
    assert _types(tokens) == [TokenType.NOT, TokenType.VARIABLE, TokenType.EOF]


def test_implies_keyword():
    tokens = logical_expression_tokenizer("a implies b")
    assert _types(tokens) == [
        TokenType.VARIABLE, TokenType.IMPLIES, TokenType.VARIABLE, TokenType.EOF
    ]


def test_iff_keyword():
    tokens = logical_expression_tokenizer("a iff b")
    assert _types(tokens) == [
        TokenType.VARIABLE, TokenType.IFF, TokenType.VARIABLE, TokenType.EOF
    ]


# ---------------------------------------------------------------------------
# symbolic / case-insensitive operators
# ---------------------------------------------------------------------------


def test_case_insensitive_keywords():
    tokens = logical_expression_tokenizer("A AND B")
    assert tokens[0].type == TokenType.VARIABLE
    assert tokens[0].value == "A"
    assert tokens[1].type == TokenType.AND
    assert tokens[1].value == "AND"


def test_implies_symbol():
    tokens = logical_expression_tokenizer("a -> b")
    assert tokens[1].type == TokenType.IMPLIES
    assert tokens[1].value == "->"


def test_iff_symbol():
    tokens = logical_expression_tokenizer("a <-> b")
    assert tokens[1].type == TokenType.IFF
    assert tokens[1].value == "<->"


def test_symbolic_and_or():
    tokens = logical_expression_tokenizer("a & b | c")
    assert _types(tokens) == [
        TokenType.VARIABLE, TokenType.AND, TokenType.VARIABLE,
        TokenType.OR, TokenType.VARIABLE, TokenType.EOF,
    ]


def test_double_ampersand_and_pipe():
    a = logical_expression_tokenizer("a && b")
    b = logical_expression_tokenizer("a || b")
    assert a[1].type == TokenType.AND and a[1].value == "&&"
    assert b[1].type == TokenType.OR and b[1].value == "||"


def test_negation_symbols():
    for sym in ("!", "~"):
        tokens = logical_expression_tokenizer(f"{sym}a")
        assert tokens[0].type == TokenType.NOT
        assert tokens[0].value == sym
        assert tokens[1].type == TokenType.VARIABLE


# ---------------------------------------------------------------------------
# comparison operators
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text, expected_type, expected_value",
    [
        ("a = b", TokenType.EQ, "="),
        ("a != b", TokenType.NEQ, "!="),
        ("a <> b", TokenType.NEQ, "<>"),
        ("a < b", TokenType.LT, "<"),
        ("a > b", TokenType.GT, ">"),
        ("a <= b", TokenType.LTE, "<="),
        ("a >= b", TokenType.GTE, ">="),
    ],
)
def test_comparison_operators(text, expected_type, expected_value):
    tokens = logical_expression_tokenizer(text)
    assert tokens[1].type == expected_type
    assert tokens[1].value == expected_value


# ---------------------------------------------------------------------------
# parentheses and grouping
# ---------------------------------------------------------------------------


def test_parentheses_around_subexpression():
    tokens = logical_expression_tokenizer("(a or b) and c")
    assert _types(tokens) == [
        TokenType.LPAREN, TokenType.VARIABLE, TokenType.OR, TokenType.VARIABLE,
        TokenType.RPAREN, TokenType.AND, TokenType.VARIABLE, TokenType.EOF,
    ]


def test_nested_parentheses():
    tokens = logical_expression_tokenizer("((a))")
    assert _types(tokens) == [
        TokenType.LPAREN, TokenType.LPAREN, TokenType.VARIABLE,
        TokenType.RPAREN, TokenType.RPAREN, TokenType.EOF,
    ]


# ---------------------------------------------------------------------------
# numbers
# ---------------------------------------------------------------------------


def test_integer_literal():
    tokens = logical_expression_tokenizer("42")
    assert tokens[0].type == TokenType.NUMBER
    assert tokens[0].value == "42"


def test_float_literal():
    tokens = logical_expression_tokenizer("3.14")
    assert tokens[0].type == TokenType.NUMBER
    assert tokens[0].value == "3.14"


def test_float_no_leading_digit():
    tokens = logical_expression_tokenizer(".5")
    assert tokens[0].type == TokenType.NUMBER
    assert tokens[0].value == ".5"


def test_number_in_expression():
    tokens = logical_expression_tokenizer("x = 100")
    assert _types(tokens) == [
        TokenType.VARIABLE, TokenType.EQ, TokenType.NUMBER, TokenType.EOF
    ]
    assert tokens[2].value == "100"


# ---------------------------------------------------------------------------
# boolean constants
# ---------------------------------------------------------------------------


def test_boolean_constants():
    tokens = logical_expression_tokenizer("true and false")
    assert _types(tokens) == [
        TokenType.TRUE, TokenType.AND, TokenType.FALSE, TokenType.EOF
    ]


def test_boolean_constants_case_insensitive():
    tokens = logical_expression_tokenizer("True Or False")
    assert _types(tokens) == [
        TokenType.TRUE, TokenType.OR, TokenType.FALSE, TokenType.EOF
    ]


# ---------------------------------------------------------------------------
# identifiers
# ---------------------------------------------------------------------------


def test_underscore_identifier():
    tokens = logical_expression_tokenizer("_foo_bar123")
    assert tokens[0].type == TokenType.VARIABLE
    assert tokens[0].value == "_foo_bar123"


def test_keyword_prefix_is_identifier():
    # "andy" looks like "and" + "y"; it must be a single VARIABLE.
    tokens = logical_expression_tokenizer("andy")
    assert _types(tokens) == [TokenType.VARIABLE, TokenType.EOF]
    assert tokens[0].value == "andy"


# ---------------------------------------------------------------------------
# whitespace, comments, strings
# ---------------------------------------------------------------------------


def test_whitespace_ignored_between_tokens():
    tokens = logical_expression_tokenizer("  a   and   b  \n  c  ")
    assert _types(tokens) == [
        TokenType.VARIABLE, TokenType.AND, TokenType.VARIABLE,
        TokenType.VARIABLE, TokenType.EOF,
    ]


def test_line_comment_is_ignored():
    tokens = logical_expression_tokenizer("a # trailing comment\nand b")
    assert _types(tokens) == [
        TokenType.VARIABLE, TokenType.AND, TokenType.VARIABLE, TokenType.EOF
    ]


def test_double_quoted_string_literal():
    tokens = logical_expression_tokenizer('"hello world"')
    assert tokens[0].type == TokenType.VARIABLE
    assert tokens[0].value == "hello world"


def test_single_quoted_string_literal():
    tokens = logical_expression_tokenizer("'foo'")
    assert tokens[0].type == TokenType.VARIABLE
    assert tokens[0].value == "foo"


# ---------------------------------------------------------------------------
# positions and structure of the token stream
# ---------------------------------------------------------------------------


def test_token_positions_tracked():
    tokens = logical_expression_tokenizer("a and b")
    assert tokens[0].position == 0   # "a"
    assert tokens[1].position == 2   # "and"
    assert tokens[2].position == 6   # "b"
    assert tokens[3].position == 7   # EOF after the "b"


def test_returns_list_of_token_instances():
    tokens = logical_expression_tokenizer("a and b")
    assert isinstance(tokens, list)
    assert all(isinstance(t, Token) for t in tokens)
    assert tokens[-1].type == TokenType.EOF


def test_complex_expression_yields_sensible_stream():
    tokens = logical_expression_tokenizer("(a and not b) or (c -> d) iff e")
    assert tokens[-1].type == TokenType.EOF
    # The exact layout must at least contain the operators we expect.
    types = set(_types(tokens))
    assert TokenType.LPAREN in types
    assert TokenType.RPAREN in types
    assert TokenType.AND in types
    assert TokenType.OR in types
    assert TokenType.NOT in types
    assert TokenType.IMPLIES in types
    assert TokenType.IFF in types


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------


def test_invalid_character_raises_value_error():
    with pytest.raises(ValueError):
        logical_expression_tokenizer("a @ b")


def test_none_raises_type_error():
    with pytest.raises(TypeError):
        logical_expression_tokenizer(None)  # type: ignore[arg-type]


def test_non_string_raises_type_error():
    with pytest.raises(TypeError):
        logical_expression_tokenizer(123)  # type: ignore[arg-type]