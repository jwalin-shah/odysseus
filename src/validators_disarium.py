"""src/validators_disarium.py - Disarium number predicate.

A Disarium number is a number in which the sum of its digits, each raised
to the power of its 1-indexed position, equals the number itself.

Examples:
    175 -> 1^1 + 7^2 + 5^3 = 1 + 49 + 125 = 175  (Disarium)
     89 -> 8^1 + 9^2      = 8 + 81      =  89  (Disarium)
     24 -> 2^1 + 4^2      = 2 + 16      =  18  (not Disarium)

The is_disarium(n) function is implemented elsewhere in this file.
Tests are co-located and run with: pytest src/validators_disarium.py -q
"""


def is_disarium(n: int) -> bool:
    """Check if n is a Disarium number.

    A Disarium number is one where the sum of its digits, each raised to the
    power of its 1-indexed position, equals the number itself.

    Parameters
    ----------
    n : int
        The integer to test. Negative numbers are not Disarium.

    Returns
    -------
    bool
        True if n is a Disarium number, False otherwise.
    """
    if not isinstance(n, int) or isinstance(n, bool):
        raise TypeError("is_disarium only accepts integers")
    if n < 0:
        return False

    digit_sum = sum(int(digit) ** (i + 1) for i, digit in enumerate(str(n)))
    return digit_sum == n


def test_is_disarium_175_returns_true():
    """AC1: is_disarium(175) must return True (1^1 + 7^2 + 5^3 = 175)."""
    assert is_disarium(175) is True


def test_is_disarium_89_returns_true():
    """AC2: is_disarium(89) must return True (8^1 + 9^2 = 89)."""
    assert is_disarium(89) is True


def test_is_disarium_24_returns_false():
    """AC3: is_disarium(24) must return False (2^1 + 4^2 = 18 != 24)."""
    assert is_disarium(24) is False


def test_is_disarium_135_returns_true():
    """AC4: is_disarium(135) must return True (1^1 + 3^2 + 5^3 = 1 + 9 + 125 = 135)."""
    assert is_disarium(135) is True


def test_is_disarium_518_returns_true():
    """AC5: is_disarium(518) must return True (5^1 + 1^2 + 8^3 = 5 + 1 + 512 = 518)."""
    assert is_disarium(518) is True


def test_is_disarium_598_returns_true():
    """AC6: is_disarium(598) must return True (5^1 + 9^2 + 8^3 = 5 + 81 + 512 = 598)."""
    assert is_disarium(598) is True


def test_is_disarium_single_digit_returns_true():
    """AC7: All single digit numbers (0-9) are Disarium (d^1 = d)."""
    for i in range(10):
        assert is_disarium(i) is True, f"{i} should be Disarium"


def test_is_disarium_zero_returns_true():
    """AC8: 0 is Disarium (sum of zero digits is 0)."""
    assert is_disarium(0) is True


def test_is_disarium_one_returns_true():
    """AC9: 1 is Disarium (1^1 = 1)."""
    assert is_disarium(1) is True


def test_is_disarium_negative_returns_false():
    """AC10: Negative numbers are not Disarium."""
    assert is_disarium(-89) is False
    assert is_disarium(-175) is False
    assert is_disarium(-1) is False


def test_is_disarium_large_non_disarium_returns_false():
    """AC11: 1000 is not Disarium (1^1 + 0^2 + 0^3 + 0^4 = 1 != 1000)."""
    assert is_disarium(1000) is False


def test_is_disarium_10_returns_false():
    """AC12: 10 is not Disarium (1^1 + 0^2 = 1 != 10)."""
    assert is_disarium(10) is False


def test_is_disarium_100_returns_false():
    """AC13: 100 is not Disarium (1^1 + 0^2 + 0^3 = 1 != 100)."""
    assert is_disarium(100) is False


def test_is_disarium_rejects_non_integer():
    """AC14: is_disarium should reject non-integer types."""
    import pytest
    with pytest.raises(TypeError):
        is_disarium(1.5)
    with pytest.raises(TypeError):
        is_disarium("175")
    with pytest.raises(TypeError):
        is_disarium(None)
    with pytest.raises(TypeError):
        is_disarium(True)


def test_is_disarium_returns_bool():
    """AC15: is_disarium must return a boolean value."""
    result_true = is_disarium(89)
    result_false = is_disarium(24)
    assert isinstance(result_true, bool)
    assert isinstance(result_false, bool)
    assert result_true is True
    assert result_false is False