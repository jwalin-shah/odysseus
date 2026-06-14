import os
import sys

# Add the src directory to the Python path so the implementation module
# can be imported regardless of where pytest is invoked from.
sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src')
)

import pytest

from missions_logical_expression_tokenizer import missions_logical_expression_tokenizer


def test_empty_expression_returns_empty_list():
    """An empty string should produce no tokens."""
    assert missions_logical_expression_tokenizer("") == []


def test_whitespace_only_returns_empty_list():
    """A string containing only whitespace should produce no tokens."""
    assert missions_logical_expression_tokenizer("   \t\n  ") == []


def test_logical_keywords():
    """AND, OR, and NOT should be tokenized as KEYWORD tokens."""
    assert missions_logical_expression_tokenizer("AND") == [('KEYWORD', 'AND')]
    assert missions_logical_expression_tokenizer("OR") == [('KEYWORD', 'OR')]
    assert missions_logical_expression_tokenizer("NOT") == [('KEYWORD', 'NOT')]


def test_identifier_tokenization():
    """Identifiers should be tokenized correctly, including those with underscores and digits."""
    assert missions_logical_expression_tokenizer("mission_active") == [
        ('IDENTIFIER', 'mission_active')
    ]
    assert missions_logical_expression_tokenizer("_flag") == [('IDENTIFIER', '_flag')]
    assert missions_logical_expression_tokenizer("var123") == [('IDENTIFIER', 'var123')]


def test_parentheses():
    """Parentheses should be tokenized as LPAREN and RPAREN."""
    assert missions_logical_expression_tokenizer("()") == [
        ('LPAREN', '('),
        ('RPAREN', ')'),
    ]


def test_double_quoted_string():
    """Double-quoted strings should be tokenized as STRING tokens."""
    assert missions_logical_expression_tokenizer('"hello"') == [('STRING', 'hello')]
    assert missions_logical_expression_tokenizer('"m1"') == [('STRING', 'm1')]


def test_single_quoted_string():
    """Single-quoted strings should be tokenized as STRING tokens."""
    assert missions_logical_expression_tokenizer("'hello'") == [('STRING', 'hello')]


def test_string_preserves_internal_spaces():
    """Spaces inside a string should be preserved in the STRING token value."""
    assert missions_logical_expression_tokenizer('"hello world"') == [
        ('STRING', 'hello world')
    ]


def test_number_tokenization():
    """Integer literals should be tokenized as NUMBER tokens."""
    assert missions_logical_expression_tokenizer("123") == [('NUMBER', '123')]
    assert missions_logical_expression_tokenizer("0") == [('NUMBER', '0')]


def test_comparison_operators():
    """All supported comparison operators should be tokenized correctly."""
    assert missions_logical_expression_tokenizer("=") == [('COMPARISON', '=')]
    assert missions_logical_expression_tokenizer("==") == [('COMPARISON', '==')]
    assert missions_logical_expression_tokenizer("!=") == [('COMPARISON', '!=')]
    assert missions_logical_expression_tokenizer("<") == [('COMPARISON', '<')]
    assert missions_logical_expression_tokenizer("<=") == [('COMPARISON', '<=')]
    assert missions_logical_expression_tokenizer(">") == [('COMPARISON', '>')]
    assert missions_logical_expression_tokenizer(">=") == [('COMPARISON', '>=')]


def test_complex_logical_expression():
    """A complex expression combining identifiers, strings, and keywords should be tokenized correctly."""
    expr = 'mission_completed("m1") AND NOT flag_set("x")'
    expected = [
        ('IDENTIFIER', 'mission_completed'),
        ('LPAREN', '('),
        ('STRING', 'm1'),
        ('RPAREN', ')'),
        ('KEYWORD', 'AND'),
        ('KEYWORD', 'NOT'),
        ('IDENTIFIER', 'flag_set'),
        ('LPAREN', '('),
        ('STRING', 'x'),
        ('RPAREN', ')'),
    ]
    assert missions_logical_expression_tokenizer(expr) == expected


def test_or_expression():
    """Simple OR expression should be tokenized correctly."""
    expr = 'a OR b'
    expected = [
        ('IDENTIFIER', 'a'),
        ('KEYWORD', 'OR'),
        ('IDENTIFIER', 'b'),
    ]
    assert missions_logical_expression_tokenizer(expr) == expected


def test_whitespace_between_tokens_is_ignored():
    """Whitespace between tokens should be skipped without producing tokens."""
    expr = "  AND   OR  "
    assert missions_logical_expression_tokenizer(expr) == [
        ('KEYWORD', 'AND'),
        ('KEYWORD', 'OR'),
    ]


def test_nested_parentheses():
    """Nested parentheses should be tokenized with matching LPAREN/RPAREN pairs."""
    expr = "(a AND (b OR c))"
    expected = [
        ('LPAREN', '('),
        ('IDENTIFIER', 'a'),
        ('KEYWORD', 'AND'),
        ('LPAREN', '('),
        ('IDENTIFIER', 'b'),
        ('KEYWORD', 'OR'),
        ('IDENTIFIER', 'c'),
        ('RPAREN', ')'),
        ('RPAREN', ')'),
    ]
    assert missions_logical_expression_tokenizer(expr) == expected


def test_function_call_with_comma_separated_arguments():
    """Commas in function argument lists should be tokenized as COMMA tokens."""
    expr = 'func("a", "b")'
    expected = [
        ('IDENTIFIER', 'func'),
        ('LPAREN', '('),
        ('STRING', 'a'),
        ('COMMA', ','),
        ('STRING', 'b'),
        ('RPAREN', ')'),
    ]
    assert missions_logical_expression_tokenizer(expr) == expected


def test_comparison_with_identifier_and_number():
    """A full comparison expression should be tokenized correctly."""
    expr = 'count >= 5'
    expected = [
        ('IDENTIFIER', 'count'),
        ('COMPARISON', '>='),
        ('NUMBER', '5'),
    ]
    assert missions_logical_expression_tokenizer(expr) == expected


def test_unterminated_string_raises_value_error():
    """An unterminated string literal should raise a ValueError."""
    with pytest.raises(ValueError):
        missions_logical_expression_tokenizer('"unterminated')


def test_invalid_character_raises_value_error():
    """An invalid character should raise a ValueError."""
    with pytest.raises(ValueError):
        missions_logical_expression_tokenizer("a & b")


def test_non_string_input_raises_type_error():
    """Passing a non-string argument should raise a TypeError."""
    with pytest.raises(TypeError):
        missions_logical_expression_tokenizer(123)
    with pytest.raises(TypeError):
        missions_logical_expression_tokenizer(None)