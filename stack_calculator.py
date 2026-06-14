"""Stack-based arithmetic expression evaluator (shunting yard algorithm)."""

from __future__ import annotations


_PREC = {'+': 1, '-': 1, '*': 2, '/': 2}
_RIGHT_ASSOC: set[str] = set()


def tokenize(expr: str) -> list[str]:
    tokens: list[str] = []
    i = 0
    while i < len(expr):
        c = expr[i]
        if c.isspace():
            i += 1
            continue
        if c.isdigit() or (c == '.' and i + 1 < len(expr) and expr[i + 1].isdigit()):
            j = i
            while j < len(expr) and (expr[j].isdigit() or expr[j] == '.'):
                j += 1
            tokens.append(expr[i:j])
            i = j
        elif c in _PREC or c in '()':
            tokens.append(c)
            i += 1
        else:
            raise ValueError(f"Unknown character: {c!r}")
    return tokens


def evaluate(expr: str) -> float:
    """Evaluate arithmetic expression string. Supports +,-,*,/ and parentheses."""
    tokens = tokenize(expr)
    output: list[float] = []
    ops: list[str] = []

    def apply_op():
        op = ops.pop()
        b, a = output.pop(), output.pop()
        if op == '+':
            output.append(a + b)
        elif op == '-':
            output.append(a - b)
        elif op == '*':
            output.append(a * b)
        elif op == '/':
            output.append(a / b)

    for tok in tokens:
        if tok not in _PREC and tok not in '()':
            output.append(float(tok))
        elif tok in _PREC:
            while (ops and ops[-1] in _PREC and
                   ((_PREC[ops[-1]] > _PREC[tok]) or
                    (_PREC[ops[-1]] == _PREC[tok] and tok not in _RIGHT_ASSOC))):
                apply_op()
            ops.append(tok)
        elif tok == '(':
            ops.append(tok)
        elif tok == ')':
            while ops and ops[-1] != '(':
                apply_op()
            if not ops:
                raise ValueError("Mismatched parentheses")
            ops.pop()

    while ops:
        apply_op()

    return output[0]
