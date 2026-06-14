"""Tests for predicates.dudeney.is_dudeney."""

import pytest

from predicates.dudeney import is_dudeney


# All six known Dudeney numbers in base 10.
KNOWN_DUDENEY = [1, 512, 4913, 5832, 17576, 19683]


@pytest.mark.parametrize("n", KNOWN_DUDENEY)
def test_known_dudeney_numbers(n):
    assert is_dudeney(n) is True


@pytest.mark.parametrize(
    "n,expected_root",
    [
        (1, 1),
        (512, 8),
        (4913, 17),
        (5832, 18),
        (17576, 26),
        (19683, 27),
    ],
)
def test_cube_root_matches_digit_sum(n, expected_root):
    # Verify the defining property directly for each known Dudeney number.
    digit_sum = sum(int(d) for d in str(n))
    assert digit_sum == expected_root
    assert is_dudeney(n) is True


def test_non_dudeney_perfect_cubes():
    # 8 = 2^3, digit sum 8 != 2
    assert is_dudeney(8) is False
    # 27 = 3^3, digit sum 9 != 3
    assert is_dudeney(27) is False
    # 64 = 4^3, digit sum 10 != 4
    assert is_dudeney(64) is False
    # 125 = 5^3, digit sum 8 != 5
    assert is_dudeney(125) is False
    # 216 = 6^3, digit sum 9 != 6
    assert is_dudeney(216) is False
    # 1000 = 10^3, digit sum 1 != 10
    assert is_dudeney(1000) is False


def test_non_perfect_cubes():
    # Numbers that are not perfect cubes cannot be Dudeney numbers.
    for n in [2, 3, 10, 50, 100, 999, 12345, 1000000]:
        assert is_dudeney(n) is False


def test_edge_cases():
    # Zero and negatives are rejected.
    assert is_dudeney(0) is False
    assert is_dudeney(-1) is False
    assert is_dudeney(-512) is False


def test_invalid_types():
    # Non-integer inputs (and booleans) must return False.
    assert is_dudeney(1.0) is False
    assert is_dudeney(8.0) is False
    assert is_dudeney("512") is False
    assert is_dudeney(None) is False
    assert is_dudeney([512]) is False
    assert is_dudeney(True) is False
    assert is_dudeney(False) is False


def test_large_non_dudeney_cube():
    # 38^3 = 54872, digit sum = 5+4+8+7+2 = 26, not a Dudeney number.
    assert is_dudeney(54872) is False
    # 100^3 = 1_000_000, digit sum = 1, not a Dudeney number.
    assert is_dudeney(1_000_000) is False