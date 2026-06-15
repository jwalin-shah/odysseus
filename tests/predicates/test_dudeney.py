"""Tests for ``predicates.dudeney.is_dudeney``."""

from __future__ import annotations

import pytest

from predicates.dudeney import is_dudeney


# All known Dudeney numbers (the first six in the OEIS sequence A003491).
KNOWN_DUDENEY = [1, 512, 4913, 5832, 17576, 19683]

# Perfect cubes whose digit sum does NOT equal the cube root. Each pair is
# (n, k) where n = k**3 and the test confirms is_dudeney(n) is False.
NON_DUDENEY_CUBES = [
    (8, 2),       # 2**3  -> digit sum 8, not 2
    (27, 3),      # 3**3  -> digit sum 9, not 3
    (64, 4),      # 4**3  -> digit sum 10, not 4
    (125, 5),     # 5**3  -> digit sum 8, not 5
    (216, 6),     # 6**3  -> digit sum 9, not 6
    (343, 7),     # 7**3  -> digit sum 10, not 7
    (729, 9),     # 9**3  -> digit sum 18, not 9
    (1000, 10),   # 10**3 -> digit sum 1, not 10
    (1331, 11),   # 11**3 -> digit sum 8, not 11
    (10648, 22),  # 22**3 -> digit sum 19, not 22
]

# Plain non-cubes, included to guard against a coincidental true return.
NON_CUBES = [0, 2, 3, 4, 5, 6, 7, 9, 10, 11, 15, 16, 17, 18, 25, 100, 999, 1000]


@pytest.mark.parametrize("n", KNOWN_DUDENEY)
def test_known_dudeney_numbers_are_true(n: int) -> None:
    assert is_dudeney(n) is True


@pytest.mark.parametrize("pair", NON_DUDENEY_CUBES)
def test_non_dudeney_cubes_are_false(pair: tuple[int, int]) -> None:
    n, k = pair
    # Sanity check on the fixtures themselves: they really are perfect cubes
    # whose digit sum differs from the cube root.
    assert k ** 3 == n
    assert is_dudeney(n) is False


@pytest.mark.parametrize("n", NON_CUBES)
def test_non_cubes_are_false(n: int) -> None:
    assert is_dudeney(n) is False


@pytest.mark.parametrize(
    "value",
    [-1, -8, -512, -1000, True, False, 1.0, 8.0, "1", "512", None],
)
def test_non_integer_or_non_positive_inputs_are_false(value: object) -> None:
    assert is_dudeney(value) is False  # type: ignore[arg-type]


def test_zero_is_false_by_convention() -> None:
    # 0 is technically 0**3 with digit sum 0, but the Dudeney sequence
    # conventionally starts at 1.
    assert is_dudeney(0) is False


def test_large_dudeney_number() -> None:
    # 262144 = 64**3, digit sum 2+6+2+1+4+4 = 19, not 64 -> not Dudeney.
    assert is_dudeney(262144) is False
    # 884736 = 96**3, digit sum 8+8+4+7+3+6 = 36, not 96 -> not Dudeney.
    assert is_dudeney(884736) is False


def test_return_type_is_bool() -> None:
    assert isinstance(is_dudeney(1), bool)
    assert isinstance(is_dudeney(2), bool)
