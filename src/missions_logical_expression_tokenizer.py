"""
Tokenizer for logical expressions used in mission definitions.

This module provides a function to tokenize a logical expression string
into a list of (token_type, token_value) tuples.

Token types:
    - KEYWORD: Logical operators (AND, OR, NOT)
    - IDENTIFIER: Variable or function names
    - STRING: Quoted string literals
    - NUMBER: Integer literals
    - LPAREN: Opening parenthesis '('
    - RPAREN: Closing parenthesis ')'
    - COMMA: Comma separator ','
    - COMPARISON: Comparison operators (=, ==, !=, <, <=, >, >=)
"""


def missions_logical_expression_tokenizer(expression):
    """
    Tokenize a logical expression string into a list of tokens.

    Each token is represented as a tuple of (token_type, token_value).
    Whitespace between tokens is ignored.

    Args:
        expression (str): The logical expression to tokenize.

    Returns:
        list: A list of (token_type, token_value) tuples.

    Raises:
        TypeError: If ``expression`` is not a string.
        ValueError: If the expression contains an unterminated string
            literal or an invalid/unexpected character.
    """
    if not isinstance(expression, str):
        raise TypeError(
            "Expression must be a string, got {}".format(type(expression).__name__)
        )

    tokens = []
    i = 0
    n = len(expression)

    while i < n:
        char = expression[i]

        # Skip whitespace
        if char.isspace():
            i += 1
            continue

        # Parentheses
        if char == '(':
            tokens.append(('LPAREN', '('))
            i += 1
            continue
        if char == ')':
            tokens.append(('RPAREN', ')'))
            i += 1
            continue

        # Comma (used to separate function arguments)
        if char == ',':
            tokens.append(('COMMA', ','))
            i += 1
            continue

        # String literals (single or double quoted)
        if char == '"' or char == "'":
            quote_char = char
            i += 1
            start = i
            while i < n and expression[i] != quote_char:
                if expression[i] == '\\' and i + 1 < n:
                    # Skip escape sequence
                    i += 2
                else:
                    i += 1
            if i >= n:
                raise ValueError(
                    "Unterminated string literal starting at position {}".format(start - 1)
                )
            value = expression[start:i]
            tokens.append(('STRING', value))
            i += 1  # Skip closing quote
            continue

        # Comparison operators: =, ==, !=, <, <=, >, >=
        if char in '=<>!':
            start = i
            i += 1
            if i < n and expression[i] == '=':
                i += 1
            tokens.append(('COMPARISON', expression[start:i]))
            continue

        # Identifiers and keywords (start with letter or underscore)
        if char.isalpha() or char == '_':
            start = i
            while i < n and (expression[i].isalnum() or expression[i] == '_'):
                i += 1
            value = expression[start:i]
            if value in ('AND', 'OR', 'NOT'):
                tokens.append(('KEYWORD', value))
            else:
                tokens.append(('IDENTIFIER', value))
            continue

        # Numbers
        if char.isdigit():
            start = i
            while i < n and expression[i].isdigit():
                i += 1
            tokens.append(('NUMBER', expression[start:i]))
            continue

        # Unknown / invalid character
        raise ValueError(
            "Unexpected character {!r} at position {}".format(char, i)
        )

    return tokens