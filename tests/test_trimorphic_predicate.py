import pytest

from trimorphic_predicate import trimorphic_predicate


@pytest.mark.parametrize("n", [1, 4, 5, 6, 9])
def test_single_digit_trimorphic(n):
    assert trimorphic_predicate(n) is True


@pytest.mark.parametrize("n", [24, 25, 49, 51, 75, 76, 99])
def test_two_digit_trimorphic(n):
    assert trimorphic_predicate(n) is True


@pytest.mark.parametrize(
    "n", [125, 249, 251, 375, 376, 499, 501, 624, 625, 749, 751, 875, 999]
)
def test_three_digit_trimorphic(n):
    assert trimorphic_predicate(n) is True


@pytest.mark.parametrize("n", [2, 3, 7, 8, 10, 11, 100, 876, 123])
def test_non_trimorphic(n):
    assert trimorphic_predicate(n) is False


def test_zero_is_trimorphic():
    # 0**3 == 0, which ends in "0", so 0 is trimorphic by the standard definition.
    assert trimorphic_predicate(0) is True


def test_handles_string_input():
    assert trimorphic_predicate("24") is True
    assert trimorphic_predicate("10") is False