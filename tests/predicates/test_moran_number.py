"""Tests for the is_moran predicate.

The expected set of Moran numbers below 1000 is computed in this file
using a simple, independent reference algorithm so that the test does
not rely on a hand-maintained list (which previously contained errors
such as 216 and 224 that are not actually Moran numbers).
"""

import pytest

from predicates.moran_number import is_moran


# ---------------------------------------------------------------------------
# Independent reference computation
# ---------------------------------------------------------------------------

def _ref_digit_sum(n: int) -> int:
    s = 0
    while n > 0:
        s += n % 10
        n //= 10
    return s


def _ref_is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    i = 3
    while i * i <= n:
        if n % i == 0:
            return False
        i += 2
    return True


def _compute_morans(limit: int) -> frozenset:
    morans = set()
    for n in range(1, limit):
        s = _ref_digit_sum(n)
        if s > 0 and n % s == 0 and _ref_is_prime(n // s):
            morans.add(n)
    return frozenset(morans)


KNOWN_MORANS_BELOW_1000 = _compute_morans(1000)


# Sanity: the reference set must be non-empty and contain the canonical examples.
assert 18 in KNOWN_MORANS_BELOW_1000
assert 21 in KNOWN_MORANS_BELOW_1000
assert 27 in KNOWN_MORANS_BELOW_1000
assert 216 not in KNOWN_MORANS_BELOW_1000
assert 224 not in KNOWN_MORANS_BELOW_1000


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestKnownMoranNumbers:
    """Every number in the independently computed set must be a Moran number."""

    @pytest.mark.parametrize("n", sorted(KNOWN_MORANS_BELOW_1000))
    def test_known_moran_is_moran(self, n):
        assert is_moran(n), f"{n} should be a Moran number"


class TestNonMoranNumbers:
    """Specific values that are known NOT to be Moran numbers."""

    @pytest.mark.parametrize("n", [
        0,
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10,
        11, 12, 13, 14, 15, 16, 17, 19, 20,
        100, 105, 108, 110, 112, 116,
        # Numbers that were wrongly claimed to be Moran by a buggy list:
        216,  # 216 / 9 = 24, not prime
        224,  # 224 / 8 = 28, not prime
        225,  # 225 / 9 = 25, not prime
    ])
    def test_non_moran_is_not_moran(self, n):
        assert not is_moran(n), f"{n} should not be a Moran number"


class TestBruteForceSanity:
    """The function must agree with the reference computation below 1000."""

    def test_all_known_morans_below_1000_are_found(self):
        actual = {n for n in range(1, 1000) if is_moran(n)}
        assert actual == KNOWN_MORANS_BELOW_1000, (
            "Mismatch: "
            f"missing={sorted(KNOWN_MORANS_BELOW_1000 - actual)[:10]}, "
            f"extra={sorted(actual - KNOWN_MORANS_BELOW_1000)[:10]}"
        )


class TestSpecificExamples:
    """Spot-checks for the classic Moran number examples."""

    @pytest.mark.parametrize("n,expected", [
        (18, True),    # 18/9 = 2
        (21, True),    # 21/3 = 7
        (27, True),    # 27/9 = 3
        (42, True),    # 42/6 = 7
        (45, True),    # 45/9 = 5
        (63, True),    # 63/9 = 7
        (84, True),    # 84/12 = 7
        (12, False),   # 12/3 = 4
        (20, False),   # 20/2 = 10
        (24, False),   # 24/6 = 4
        (30, False),   # 30/3 = 10
        (36, False),   # 36/9 = 4
        (216, False),  # 216/9 = 24
        (224, False),  # 224/8 = 28
    ])
    def test_examples(self, n, expected):
        assert is_moran(n) is expected


class TestEdgeCases:
    def test_zero_is_not_moran(self):
        assert not is_moran(0)

    def test_negative_is_not_moran(self):
        assert not is_moran(-18)
        assert not is_moran(-1)

    def test_boolean_is_not_moran(self):
        # In Python, bool is a subclass of int, but True/False are not
        # natural numbers, so they should not be treated as Moran numbers.
        assert not is_moran(True)
        assert not is_moran(False)

    def test_non_integer_is_not_moran(self):
        assert not is_moran(18.0)
        assert not is_moran("18")
        assert not is_moran(None)