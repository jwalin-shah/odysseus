import os
import sys

import pytest

# Ensure the src directory is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from missions_recursive_josephus_survivor_locator import josephus_survivor


@pytest.mark.parametrize(
    "n, k, expected",
    [
        # k == 2 — well known Josephus sequence (0-indexed)
        (1, 2, 0),
        (2, 2, 0),
        (3, 2, 2),
        (4, 2, 0),
        (5, 2, 2),
        (6, 2, 4),
        (7, 2, 6),
        (8, 2, 0),
        (9, 2, 2),
        (10, 2, 4),
        # k == 3
        (1, 3, 0),
        (2, 3, 1),
        (3, 3, 1),
        (4, 3, 0),
        (5, 3, 3),
        (6, 3, 0),
        (7, 3, 3),
        # k == 1 — everyone eliminated in order, last person survives
        (1, 1, 0),
        (3, 1, 2),
        (5, 1, 4),
        (10, 1, 9),
        # Larger values
        (41, 3, 30),
        (100, 2, 72),
    ],
)
def test_known_values(n, k, expected):
    assert josephus_survivor(n, k) == expected


def test_single_person_any_k():
    # With only one person, that person is always the survivor
    for k in (1, 2, 3, 5, 10):
        assert josephus_survivor(1, k) == 0


def test_k_equals_one_returns_last_index():
    # When k=1 we eliminate people in order, so the last (n-1) survives
    assert josephus_survivor(7, 1) == 6
    assert josephus_survivor(1, 1) == 0
    assert josephus_survivor(20, 1) == 19


def test_invalid_n_raises_value_error():
    with pytest.raises(ValueError):
        josephus_survivor(0, 2)
    with pytest.raises(ValueError):
        josephus_survivor(-5, 2)


def test_invalid_k_raises_value_error():
    with pytest.raises(ValueError):
        josephus_survivor(5, 0)
    with pytest.raises(ValueError):
        josephus_survivor(5, -1)


def test_result_is_within_range():
    for n in range(1, 20):
        for k in (1, 2, 3, 4, 5):
            result = josephus_survivor(n, k)
            assert 0 <= result < n