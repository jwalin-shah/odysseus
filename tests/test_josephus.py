"""Tests for the josephus module.

The tests cover:

* well-known Josephus problem instances,
* algebraic properties of the closed-form solution,
* a brute-force cross-check,
* the public :func:`josephus_sequence` helper,
* error handling for invalid input.
"""

import os
import sys

# Ensure the project root (which contains ``josephus.py``) is importable
# regardless of the working directory the tests are launched from.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from josephus import josephus, josephus_sequence


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _brute_force(n: int, k: int) -> int:
    """Naive list-based simulation used to cross-check :func:`josephus`."""
    people = list(range(1, n + 1))
    idx = 0
    while len(people) > 1:
        idx = (idx + k - 1) % len(people)
        people.pop(idx)
    return people[0]


# ---------------------------------------------------------------------------
# Known-value tests
# ---------------------------------------------------------------------------
class TestKnownValues:
    """Well-known results from the Josephus problem."""

    def test_five_two(self):
        # Classic example: 5 people, every 2nd eliminated -> survivor is 3.
        assert josephus(5, 2) == 3

    def test_seven_three(self):
        # 7 people, k=3 -> survivor is 4.
        assert josephus(7, 3) == 4

    def test_six_five(self):
        # 6 people, k=5 -> survivor is 1.
        assert josephus(6, 5) == 1

    def test_forty_one_three(self):
        # Classic large instance; survivor is 31.
        assert josephus(41, 3) == 31

    def test_n_equals_one(self):
        # With a single person, that person always survives.
        assert josephus(1, 1) == 1
        assert josephus(1, 2) == 1
        assert josephus(1, 999) == 1

    @pytest.mark.parametrize(
        "n, k, expected",
        [
            (2, 2, 1),
            (3, 2, 3),
            (4, 2, 1),
            (5, 2, 3),
            (6, 2, 5),
            (7, 2, 7),
            (8, 2, 1),
            (9, 2, 3),
            (10, 2, 5),
        ],
    )
    def test_k2_known_values(self, n, k, expected):
        assert josephus(n, k) == expected


# ---------------------------------------------------------------------------
# Property-based tests
# ---------------------------------------------------------------------------
class TestProperties:
    """Properties that must hold for any valid ``(n, k)`` pair."""

    @pytest.mark.parametrize("n", [1, 2, 5, 10, 50, 100, 1000])
    def test_k_equals_one(self, n):
        # With k=1 the survivors are removed 1, 2, ..., n-1, so n survives.
        assert josephus(n, 1) == n

    def test_returns_integer(self):
        # The result must be a plain int (not e.g. a numpy scalar or float).
        result = josephus(7, 3)
        assert isinstance(result, int)
        assert 1 <= result <= 7

    def test_matches_brute_force_small(self):
        # Cross-check the closed-form solution against a brute-force
        # simulation over a representative grid of inputs.
        for n in range(1, 25):
            for k in range(1, 12):
                assert josephus(n, k) == _brute_force(n, k), (
                    f"mismatch at n={n}, k={k}"
                )

    def test_survivor_in_range(self):
        # The reported survivor must always be a valid position.
        for n in range(1, 30):
            for k in range(1, 15):
                assert 1 <= josephus(n, k) <= n


# ---------------------------------------------------------------------------
# Sequence tests
# ---------------------------------------------------------------------------
class TestJosephusSequence:
    """Direct tests for :func:`josephus_sequence`."""

    def test_five_two_order(self):
        assert josephus_sequence(5, 2) == [2, 4, 1, 5, 3]

    def test_seven_three_order(self):
        # 1 2 3 4 5 6 7 -> 3 6 2 7 5 1 4
        assert josephus_sequence(7, 3) == [3, 6, 2, 7, 5, 1, 4]

    def test_single_person(self):
        assert josephus_sequence(1, 5) == [1]

    def test_sequence_length_is_n(self):
        for n in [1, 2, 5, 10, 25]:
            assert len(josephus_sequence(n, 3)) == n

    def test_sequence_contains_all_positions(self):
        # Every position 1..n must appear exactly once.
        for n, k in [(5, 2), (7, 3), (10, 4), (20, 7)]:
            seq = josephus_sequence(n, k)
            assert sorted(seq) == list(range(1, n + 1))

    def test_sequence_ends_with_survivor(self):
        # The last element must be the survivor returned by josephus().
        for n, k in [(5, 2), (7, 3), (6, 5), (10, 4), (12, 7), (20, 3)]:
            assert josephus_sequence(n, k)[-1] == josephus(n, k)

    def test_sequence_matches_brute_force(self):
        # The simulation helper in this test file and the production
        # implementation must agree on the full ordering.
        def _brute_order(n, k):
            people = list(range(1, n + 1))
            order = []
            idx = 0
            while people:
                idx = (idx + k - 1) % len(people)
                order.append(people.pop(idx))
            return order

        for n in range(1, 15):
            for k in range(1, 10):
                assert josephus_sequence(n, k) == _brute_order(n, k)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------
class TestErrors:
    """Invalid input must raise rather than silently misbehave."""

    @pytest.mark.parametrize("n", [0, -1, -10])
    def test_invalid_n_raises(self, n):
        with pytest.raises(ValueError):
            josephus(n, 2)
        with pytest.raises(ValueError):
            josephus_sequence(n, 2)

    @pytest.mark.parametrize("k", [0, -1, -5])
    def test_invalid_k_raises(self, k):
        with pytest.raises(ValueError):
            josephus(5, k)
        with pytest.raises(ValueError):
            josephus_sequence(5, k)

    @pytest.mark.parametrize("bad", [1.5, "2", None, [2], 2.0])
    def test_non_integer_n_raises(self, bad):
        with pytest.raises(TypeError):
            josephus(bad, 2)

    @pytest.mark.parametrize("bad", [1.5, "2", None, [2], 2.0])
    def test_non_integer_k_raises(self, bad):
        with pytest.raises(TypeError):
            josephus(5, bad)

    @pytest.mark.parametrize("bad", [True, False])
    def test_bool_rejected(self, bad):
        # ``bool`` is a subclass of ``int``; make sure we reject it
        # rather than silently accepting it.
        with pytest.raises(TypeError):
            josephus(bad, 2)
        with pytest.raises(TypeError):
            josephus(2, bad)