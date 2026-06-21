"""keith_number_predicate — Detect whether an integer is a Keith number.

A Keith number is an integer n that appears in the Fibonacci-like sequence
generated from its own base-10 digits. The sequence starts with the digits of
n (in order, most-significant first) and each subsequent term is the sum of
the previous d terms, where d is the number of digits of n. n is a Keith
number iff it appears somewhere in that sequence.

Reference: https://en.wikipedia.org/wiki/Keith_number
"""


def _digits(n: int) -> list[int]:
    """Return the base-10 digits of n, most-significant first.

    n is assumed positive (callers gate zero/negative upstream).
    """
    out: list[int] = []
    while n > 0:
        out.append(n % 10)
        n //= 10
    out.reverse()
    return out


def keith_number_predicate(n: int) -> bool:
    """Return True iff n is a Keith number.

    A single-digit, zero, or negative integer is never a Keith number — the
    sequence requires at least two seed digits to be distinct from n itself,
    and the convention is that Keith numbers are >= 10.
    """
    if n < 10:
        return False
    seeds = _digits(n)
    d = len(seeds)
    seq = list(seeds)
    # Bound the search: a non-Keith number will exceed it well before we
    # loop forever. 10000 iterations is comfortably above the chain length
    # for every Keith number < 10**15 and short enough to be cheap for
    # non-Keith inputs.
    for _ in range(10000):
        nxt = sum(seq[-d:])
        if nxt == n:
            return True
        if nxt > n and n not in seq:
            # The sequence is monotonically increasing past d terms, so
            # if we've already passed n without hitting it we're done.
            return False
        seq.append(nxt)
    return False
