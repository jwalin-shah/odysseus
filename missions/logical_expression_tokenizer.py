"""
Logical expression tokenizer.

Converts a string logical expression into a list of tokens that can be
consumed by a parser to build an Abstract Syntax Tree (AST).

Supported syntax
----------------
* Logical operators (case-insensitive keywords):
      and, or, not, implies, iff
* Symbolic operators:
      &, &&, *, |, ||, +, !, ~, ->, <->, =>   (and / or / not / implies / iff)
* Comparison operators:
      =, !=, <>, <, >, <=, >=
* Structural:
      ( )
* Variables:    [A-Za-z_][A-Za-z0-9_]*
* Numbers:      integers and floats (e.g. 42, 3.14, .5)
* Boolean constants: true, false
* String literals: "..." or '...'   (lexed as VARIABLE)
* Whitespace is ignored.
* ``#`` starts a line comment that runs to the next newline.

The token stream always ends with a single EOF token.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import List


class TokenType(Enum):
    """Enumeration of every token category produced by the tokenizer."""

    # Structural
    LPAREN = auto()
    RPAREN = auto()
    EOF = auto()

    # Logical operators (keyword form, case-insensitive)
    AND = auto()
    OR = auto()
    NOT = auto()
    IMPLIES = auto()
    IFF = auto()

    # Comparison operators
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()

    # Atoms
    VARIABLE = auto()
    NUMBER = auto()
    TRUE = auto()
    FALSE = auto()


@dataclass
class Token:
    """A single token: its category, raw text and the offset where it started."""

    type: TokenType
    value: str
    position: int = 0

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Token({self.type.name}, {self.value!r}, pos={self.position})"


_KEYWORDS = {
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "implies": TokenType.IMPLIES,
    "iff": TokenType.IFF,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
}


def logical_expression_tokenizer(expression: str) -> List[Token]:
    """
    Tokenize ``expression`` into a list of :class:`Token` objects.

    Parameters
    ----------
    expression:
        The source text of the logical expression.

    Returns
    -------
    list[Token]
        The token stream. The final element is always ``Token(EOF, '', n)``
        where ``n`` is the length of the input.

    Raises
    ------
    TypeError
        If ``expression`` is not a string (including ``None``).
    ValueError
        If an unrecognized character is encountered.

    Examples
    --------
    >>> toks = logical_expression_tokenizer("a and not b")
    >>> [t.type.name for t in toks]
    ['VARIABLE', 'AND', 'NOT', 'VARIABLE', 'EOF']
    >>> toks[0].value, toks[0].position
    ('a', 0)
    """
    if expression is None:
        raise TypeError("expression must be a string, not None")
    if not isinstance(expression, str):
        raise TypeError(
            f"expression must be a string, got {type(expression).__name__}"
        )

    tokens: List[Token] = []
    i = 0
    n = len(expression)

    while i < n:
        c = expression[i]

        # ---- whitespace ----------------------------------------------------
        if c.isspace():
            i += 1
            continue

        # ---- line comment --------------------------------------------------
        if c == "#":
            while i < n and expression[i] != "\n":
                i += 1
            continue

        # ---- three-character operators ------------------------------------
        if i + 2 < n and expression[i:i + 3] == "<->":
            tokens.append(Token(TokenType.IFF, "<->", i))
            i += 3
            continue

        # ---- two-character operators --------------------------------------
        if i + 1 < n:
            two = expression[i:i + 2]
            if two == "->":
                tokens.append(Token(TokenType.IMPLIES, two, i))
                i += 2
                continue
            if two == "!=" or two == "<>":
                tokens.append(Token(TokenType.NEQ, two, i))
                i += 2
                continue
            if two == "<=":
                tokens.append(Token(TokenType.LTE, two, i))
                i += 2
                continue
            if two == ">=":
                tokens.append(Token(TokenType.GTE, two, i))
                i += 2
                continue
            if two == "&&":
                tokens.append(Token(TokenType.AND, two, i))
                i += 2
                continue
            if two == "||":
                tokens.append(Token(TokenType.OR, two, i))
                i += 2
                continue

        # ---- single-character structural ----------------------------------
        if c == "(":
            tokens.append(Token(TokenType.LPAREN, c, i))
            i += 1
            continue
        if c == ")":
            tokens.append(Token(TokenType.RPAREN, c, i))
            i += 1
            continue

        # ---- single-character logical -------------------------------------
        if c in "&*":
            tokens.append(Token(TokenType.AND, c, i))
            i += 1
            continue
        if c in "|+":
            tokens.append(Token(TokenType.OR, c, i))
            i += 1
            continue
        if c in "!~¬":
            tokens.append(Token(TokenType.NOT, c, i))
            i += 1
            continue

        # ---- single-character comparison ----------------------------------
        if c == "=":
            tokens.append(Token(TokenType.EQ, c, i))
            i += 1
            continue
        if c == "<":
            tokens.append(Token(TokenType.LT, c, i))
            i += 1
            continue
        if c == ">":
            tokens.append(Token(TokenType.GT, c, i))
            i += 1
            continue

        # ---- number --------------------------------------------------------
        if c.isdigit() or (
            c == "." and i + 1 < n and expression[i + 1].isdigit()
        ):
            start = i
            has_dot = False
            while i < n and (
                expression[i].isdigit()
                or (expression[i] == "." and not has_dot)
            ):
                if expression[i] == ".":
                    has_dot = True
                i += 1
            tokens.append(Token(TokenType.NUMBER, expression[start:i], start))
            continue

        # ---- identifier / keyword -----------------------------------------
        if c.isalpha() or c == "_":
            start = i
            while i < n and (expression[i].isalnum() or expression[i] == "_"):
                i += 1
            word = expression[start:i]
            lower = word.lower()
            if lower in _KEYWORDS:
                tokens.append(Token(_KEYWORDS[lower], word, start))
            else:
                tokens.append(Token(TokenType.VARIABLE, word, start))
            continue

        # ---- string literal (treated as VARIABLE) -------------------------
        if c in "'\"":
            quote = c
            start = i
            i += 1
            value_chars: List[str] = []
            while i < n and expression[i] != quote:
                if expression[i] == "\\" and i + 1 < n:
                    value_chars.append(expression[i + 1])
                    i += 2
                else:
                    value_chars.append(expression[i])
                    i += 1
            if i < n:
                i += 1  # consume closing quote
            tokens.append(Token(TokenType.VARIABLE, "".join(value_chars), start))
            continue

        # ---- anything else is an error ------------------------------------
        raise ValueError(
            f"Unexpected character {c!r} at position {i} in expression: "
            f"{expression!r}"
        )

    tokens.append(Token(TokenType.EOF, "", n))
    return tokens


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    import pprint

    pprint.pprint(
        [
            (t.type.name, t.value, t.position)
            for t in logical_expression_tokenizer(
                "(a and not b) or (c -> d) iff e"
            )
        ]
    )