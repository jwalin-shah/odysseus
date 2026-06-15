"""Tests for predicates.dudeney.is_dudeney."""
import pytest

from predicates.dudeney import is_dudeney


KNOWN_DUDENEY = [1, 512, 4913, 5832, 17576, 19683]


@pytest.mark.parametrize("n", KNOWN_DUDENEY)
def test_known_dudeney_numbers_are_true(n):
    assert is_dudeney(n) is True


@pytest.mark.parametrize(
    "n",
    [
        0,  # not a positive integer
        2, 3, 4, 5, 6, 7, 8, 9, 10,  # not perfect cubes (or wrong digit sum)
        27,  # 3^3 but digit sum 9 != 3
        64,  # 4^3 but digit sum 10 != 4
        125,  # 5^3 but digit sum 8 != 5
        216,  # 6^3 but digit sum 9 != 6
        729,  # 9^3 but digit sum 18 != 9
        1000,  # 10^3 but digit sum 1 != 10
        999,  # not a perfect cube
        46656,  # 36^3 but digit sum 27 != 36
    ],
)
def test_non_dudeney_numbers_are_false(n):
    assert is_dudeney(n) is False


@pytest.mark.parametrize("n", [-1, -8, -27, -512, -1000])
def test_negative_inputs_are_false(n):
    assert is_dudeney(n) is False


def test_return_type_is_bool():
    assert isinstance(is_dudeney(1), bool)
    assert isinstance(is_dudeney(2), bool)
    assert isinstance(is_dudeney(0), bool)
    assert isinstance(is_dudeney(-1), bool)
