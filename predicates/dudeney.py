"""Dudeney number predicate.

A Dudeney number is a positive integer that is a perfect cube and whose
sum of decimal digits equals its cube root. The known Dudeney numbers
under 100000 are: 1, 512, 4913, 5832, 17576, 19683.
"""


def is_dudeney(n: int) -> bool:
    """Return True if n is a Dudeney number."""
    if not isinstance(n, int) or n < 1:
        return False

    # Approximate integer cube root. Round to nearest int and then verify
    # against the few neighbouring candidates to guard against floating-point
    # error near large perfect cubes.
    approx = round(n ** (1 / 3))
    digit_sum = sum(int(d) for d in str(n))

    for root in (approx - 1, approx, approx + 1):
        if root >= 1 and root ** 3 == n and digit_sum == root:
            return True
    return False
