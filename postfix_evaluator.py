"""Postfix (Reverse Polish Notation) expression evaluator.

Evaluates arithmetic expressions written in postfix notation where
operators follow their operands, e.g. ``"3 4 +"`` evaluates to ``7``.

Supported operators: ``+``, ``-``, ``*``, ``/``, ``//``, ``%``, ``**``.
Operands may be integers or floats (including negative numbers and
scientific notation).
"""

from __future__ import annotations


def postfix_evaluator(expression):
    """Evaluate a postfix (Reverse Polish Notation) expression.

    Parameters
    ----------
    expression : str
        A postfix expression with space-separated tokens. Each operand
        or operator must be separated by whitespace.

    Returns
    -------
    int | float
        The result of evaluating the expression. Integer-looking tokens
        are stored as ``int``; tokens containing a decimal point or
        scientific notation become ``float``.

    Raises
    ------
    TypeError
        If ``expression`` is not a string.
    ValueError
        If the expression is empty, contains an unknown token, has an
        invalid structure (e.g. too few operands, leftover values on
        the stack), or cannot be parsed.
    ZeroDivisionError
        If a division (``/``, ``//``) or modulo (``%``) operation is
        attempted with a zero divisor.
    """
    if not isinstance(expression, str):
        raise TypeError(
            f"Expression must be a string, got {type(expression).__name__}"
        )

    tokens = expression.split()
    if not tokens:
        raise ValueError("Expression is empty")

    operators = {
        "+": lambda a, b: a + b,
        "-": lambda a, b: a - b,
        "*": lambda a, b: a * b,
        "/": lambda a, b: a / b,
        "//": lambda a, b: a // b,
        "%": lambda a, b: a % b,
        "**": lambda a, b: a ** b,
    }

    stack = []
    for token in tokens:
        if token in operators:
            if len(stack) < 2:
                raise ValueError(
                    f"Invalid expression: not enough operands for "
                    f"operator '{token}'"
                )
            b = stack.pop()
            a = stack.pop()
            if token in ("/", "//", "%") and b == 0:
                raise ZeroDivisionError(
                    f"Division or modulo by zero for operator '{token}'"
                )
            stack.append(operators[token](a, b))
        else:
            try:
                stack.append(int(token))
            except ValueError:
                try:
                    stack.append(float(token))
                except ValueError:
                    raise ValueError(f"Invalid token: '{token}'")

    if len(stack) != 1:
        raise ValueError(
            f"Invalid expression: {len(stack)} value(s) left on the stack "
            f"(expected exactly 1)"
        )

    return stack[0]