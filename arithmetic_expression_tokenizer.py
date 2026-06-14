"""arithmetic_expression_tokenizer: Tokenize arithmetic expressions.

The public entry point is :func:`arithmetic_expression_tokenizer`, which
converts a string containing an arithmetic expression into a list of
typed tokens. Whitespace is ignored. Unrecognised characters raise
:exc:`ValueError`; non-string input raises :exc:`TypeError`.

Token types returned:

* ``"NUMBER"``   - integer or decimal numeric literal (e.g. ``"3"``,
                   ``"3.14"``, ``".5"``).
* ``"OPERATOR"`` - one of ``+ - * / ** //``.
* ``"LPAREN"``   - ``(``.
* ``"RPAREN"``   - ``)``.

The tokenizer does not decide whether a ``-`` is unary or binary; that
is the parser's responsibility.
"""

from __future__ import annotations

from typing import List, Tuple

Token = Tuple[str, str]


def arithmetic_expression_tokenizer(expression: str) -> List[Token]:
    """Tokenize an arithmetic expression.

    Parameters
    ----------
    expression:
        The string to tokenize.

    Returns
    -------
    list[tuple[str, str]]
        A list of ``(token_type, token_value)`` pairs in the order they
        appear in *expression*. Whitespace tokens are skipped.

    Raises
    ------
    TypeError
        If *expression* is not a :class:`str`.
    ValueError
        If *expression* contains an unknown character or a malformed
        numeric literal.
    """
    if not isinstance(expression, str):
        raise TypeError(
            "arithmetic_expression_tokenizer expected str, got "
            f"{type(expression).__name__}"
        )

    tokens: List[Token] = []
    i = 0
    n = len(expression)

    while i < n:
        ch = expression[i]

        # --- whitespace -------------------------------------------------
        if ch.isspace():
            i += 1
            continue

        # --- number (digits with at most one decimal point) ------------
        if ch.isdigit() or ch == ".":
            j = i
            seen_dot = False
            has_digit = False
            while j < n:
                c = expression[j]
                if c.isdigit():
                    has_digit = True
                    j += 1
                elif c == "." and not seen_dot:
                    seen_dot = True
                    j += 1
                else:
                    break
            if not has_digit:
                raise ValueError(
                    f"Invalid number starting at position {i}: "
                    f"{expression[i:j]!r}"
                )
            tokens.append(("NUMBER", expression[i:j]))
            i = j
            continue

        # --- two-character operators (``**`` and ``//``) ---------------
        if i + 1 < n and expression[i:i + 2] in ("**", "//"):
            tokens.append(("OPERATOR", expression[i:i + 2]))
            i += 2
            continue

        # --- single-character operators --------------------------------
        if ch in "+-*/":
            tokens.append(("OPERATOR", ch))
            i += 1
            continue

        # --- parentheses ------------------------------------------------
        if ch == "(":
            tokens.append(("LPAREN", ch))
            i += 1
            continue
        if ch == ")":
            tokens.append(("RPAREN", ch))
            i += 1
            continue

        # --- anything else is an error ---------------------------------
        raise ValueError(
            f"Unexpected character {ch!r} at position {i} in {expression!r}"
        )

    return tokens


__all__ = ["arithmetic_expression_tokenizer", "Token"]