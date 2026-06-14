"""Tests for ``missions.recursive_josephus_survivor_locator``."""
import os
import sys

# Make the project root importable so that ``from missions import ...`` works
# regardless of where pytest is invoked from.
_PROJECT_ROOT = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", ".."
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from missions.recursive_josephus_survivor_locator import (
    recursive_josephus_survivor_locator,
)


# ---------------------------------------------------------------------------
# Known-value tests against hand-computed / textbook answers
# ---------------------------------------------------------------------------


def test_josephus_5_people_k2():
    """Classic textbook example: J(5, 2) == 3."""
    assert recursive_josephus_survivor_locator(5, 2) == 3


def test_josephus_7_people_k3():
    """J(7, 3) == 4."""
    assert recursive_josephus_survivor_locator(7, 3) == 4


def test_josephus_6_people_k2():
    """J(6, 2) == 5."""
    assert recursive_josephus_survivor_locator(6, 2) == 5


def test_josephus_8_people_k2():
    """J(8, 2) == 1 (the cycle restarts)."""
    assert recursive_josephus_survivor_locator(8, 2) == 1


def test_josephus_5_people_k5():
    """J(5, 5) == 2."""
    assert recursive_josephus_survivor_locator(5, 5) == 2


def test_josephus_10_people_k3():
    """J(10, 3) == 4."""
    assert recursive_josephus_survivor_locator(10, 3) == 4


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


def test_single_person_returns_one():
    """With n == 1, the only person in the circle is the survivor."""
    assert recursive_josephus_survivor_locator(1, 1) == 1
    assert recursive_josephus_survivor_locator(1, 2) == 1
    assert recursive_josephus_survivor_locator(1, 5) == 1
    assert recursive_josephus_survivor_locator(1, 100) == 1


def test_k_equals_one_last_person_survives():
    """When k == 1, the first person is eliminated and the last survives."""
    assert recursive_josephus_survivor_locator(2, 1) == 2
    assert recursive_josephus_survivor_locator(5, 1) == 5
    assert recursive_josephus_survivor_locator(10, 1) == 10


def test_two_people_k2():
    """J(2, 2) == 1: the second person is eliminated first."""
    assert recursive_josephus_survivor_locator(2, 2) == 1


def test_zero_people_returns_zero():
    """``n == 0`` is invalid; the function signals failure with 0."""
    assert recursive_josephus_survivor_locator(0, 2) == 0


def test_zero_k_returns_zero():
    """``k == 0`` is invalid; the function signals failure with 0."""
    assert recursive_josephus_survivor_locator(5, 0) == 0


def test_negative_n_returns_zero():
    """Negative ``n`` is invalid; the function returns 0."""
    assert recursive_josephus_survivor_locator(-3, 2) == 0


def test_negative_k_returns_zero():
    """Negative ``k`` is invalid; the function returns 0."""
    assert recursive_josephus_survivor_locator(5, -2) == 0


def test_non_integer_n_returns_zero():
    """Non-integer ``n`` is invalid; the function returns 0."""
    assert recursive_josephus_survivor_locator(5.5, 2) == 0
    assert recursive_josephus_survivor_locator("5", 2) == 0
    assert recursive_josephus_survivor_locator(None, 2) == 0


def test_non_integer_k_returns_zero():
    """Non-integer ``k`` is invalid; the function returns 0."""
    assert recursive_josephus_survivor_locator(5, 2.5) == 0
    assert recursive_josephus_survivor_locator(5, "2") == 0
    assert recursive_josephus_survivor_locator(5, None) == 0


def test_bool_arguments_are_rejected():
    """Booleans must not be silently accepted in place of integers."""
    assert recursive_josephus_survivor_locator(True, 2) == 0
    assert recursive_josephus_survivor_locator(5, False) == 0


# ---------------------------------------------------------------------------
# Property-style tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "n, k, expected",
    [
        (1, 1, 1),
        (1, 7, 1),
        (2, 1, 2),
        (2, 2, 1),
        (3, 2, 3),
        (4, 2, 1),
        (5, 2, 3),
        (6, 2, 5),
        (7, 2, 7),
        (5, 3, 4),
        (7, 3, 4),
        (10, 3, 4),
        (5, 5, 2),
        (6, 5, 1),
    ],
)
def test_parametrized_known_values(n, k, expected):
    """Verify a broad table of well-known Josephus results."""
    assert recursive_josephus_survivor_locator(n, k) == expected


def test_result_within_valid_range_small():
    """The survivor position must always be in the range ``[1, n]``."""
    for n in range(1, 15):
        for k in range(1, 10):
            result = recursive_josephus_survivor_locator(n, k)
            assert 1 <= result <= n, (
                f"Out-of-range result for n={n}, k={k}: {result}"
            )


def test_recursive_handles_moderately_large_n():
    """The recursion should comfortably handle moderate input sizes."""
    result = recursive_josephus_survivor_locator(100, 7)
    assert 1 <= result <= 100


def test_function_is_pure():
    """Calling the function multiple times must yield the same result."""
    first = recursive_josephus_survivor_locator(12, 4)
    second = recursive_josephus_survivor_locator(12, 4)
    third = recursive_josephus_survivor_locator(12, 4)
    assert first == second == third