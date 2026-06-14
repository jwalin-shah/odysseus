"""Reverse Polish Notation (RPN) expression evaluator."""

import operator
from typing import Any, List, Tuple, Union

# Supported binary operators. Using the `operator` module makes the
# implementation concise and easy to extend.
OPERATORS = {
    "+": operator.add,
    "-": operator.sub,
    "*": operator.mul,
    "/": operator.truediv,
    "**": operator.pow,
}


def _to_number(token: str):
    """Convert a string token to a number (int preferred, else float)."""
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        raise ValueError(f"invalid token: {token!r}")


def rpn_eval(expr: Union[str, List[Any], Tuple[Any, ...]]) -> Union[int, float]:
    """Evaluate a Reverse Polish Notation (postfix) expression.

    The expression may be supplied as a space-separated string, or as a
    list/tuple of tokens. Each numeric token is pushed onto an internal
    stack. An operator token pops the top two values, applies the binary
    operation, and pushes the result back. The final stack value is
    returned.

    Args:
        expr: A space-separated string, or a list/tuple of tokens where
            each token is either a number (``int``/``float``) or an
            operator string in ``{"+", "-", "*", "/", "**"}``.

    Returns:
        The single value left on the stack after evaluation.

    Raises:
        TypeError: If ``expr`` is not a string/list/tuple, or if a
            token has an unsupported type.
        ValueError: If ``expr`` is empty, contains an unknown operator
            or non-numeric token, or is not a well-formed RPN expression
            (too few / too many operands).
        ZeroDivisionError: If a division by zero is attempted.
    """
    # ---- Tokenise ----------------------------------------------------
    if isinstance(expr, str):
        tokens = expr.split()
    elif isinstance(expr, (list, tuple)):
        tokens = list(expr)
    else:
        raise TypeError(
            f"expr must be a string, list, or tuple, got {type(expr).__name__}"
        )

    if not tokens:
        raise ValueError("empty expression")

    # ---- Evaluate ----------------------------------------------------
    stack: List[Union[int, float]] = []

    for token in tokens:
        if isinstance(token, str) and token in OPERATORS:
            # Operator: need two operands on the stack.
            if len(stack) < 2:
                raise ValueError(
                    f"invalid RPN: not enough operands for operator {token!r}"
                )
            b = stack.pop()
            a = stack.pop()
            # ZeroDivisionError from operator.truediv propagates naturally.
            stack.append(OPERATORS[token](a, b))
        elif isinstance(token, bool):
            # Guard against bool being treated as int silently.
            raise TypeError(f"invalid token type: {type(token).__name__}")
        elif isinstance(token, (int, float)):
            stack.append(token)
        elif isinstance(token, str):
            stack.append(_to_number(token))
        else:
            raise TypeError(f"invalid token type: {type(token).__name__}")

    if len(stack) != 1:
        raise ValueError(
            f"invalid RPN: expression leaves {len(stack)} values on the "
            f"stack (expected exactly 1)"
        )

    return stack[0]


if __name__ == "__main__":  # pragma: no cover - simple manual smoke test
    import sys

    if len(sys.argv) > 1:
        print(rpn_eval(" ".join(sys.argv[1:])))
    else:
        print("Usage: python rpn_eval.py '<rpn expression>'")