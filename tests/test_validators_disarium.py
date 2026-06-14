"""tests/test_validators_disarium.py - Tests for the Disarium number predicate.

A Disarium number is a number in which the sum of its digits, each raised
to the power of its 1-indexed position, equals the number itself.

Run with: pytest tests/test_validators_disarium.py -q
"""

import pytest

from src.validators_disarium import is_disarium


class TestIsDisariumKnownDisariumNumbers:
    """Tests for known Disarium numbers."""

    def test_0_is_disarium(self):
        """0 is a Disarium number (sum of no digits is 0, equal to 0)."""
        assert is_disarium(0) is True

    def test_single_digit_numbers_are_disarium(self):
        """All single digit numbers 0-9 are Disarium (d^1 == d)."""
        for n in range(10):
            assert is_disarium(n) is True, f"{n} should be Disarium"

    def test_89_is_disarium(self):
        """89 is Disarium: 8^1 + 9^2 = 8 + 81 = 89."""
        assert is_disarium(89) is True

    def test_135_is_disarium(self):
        """135 is Disarium: 1^1 + 3^2 + 5^3 = 1 + 9 + 125 = 135."""
        assert is_disarium(135) is True

    def test_175_is_disarium(self):
        """175 is Disarium: 1^1 + 7^2 + 5^3 = 1 + 49 + 125 = 175."""
        assert is_disarium(175) is True

    def test_518_is_disarium(self):
        """518 is Disarium: 5^1 + 1^2 + 8^3 = 5 + 1 + 512 = 518."""
        assert is_disarium(518) is True

    def test_598_is_disarium(self):
        """598 is Disarium: 5^1 + 9^2 + 8^3 = 5 + 81 + 512 = 598."""
        assert is_disarium(598) is True


class TestIsDisariumNonDisariumNumbers:
    """Tests for numbers that are NOT Disarium."""

    def test_10_is_not_disarium(self):
        """10 is not Disarium: 1^1 + 0^2 = 1 != 10."""
        assert is_disarium(10) is False

    def test_24_is_not_disarium(self):
        """24 is not Disarium: 2^1 + 4^2 = 2 + 16 = 18 != 24."""
        assert is_disarium(24) is False

    def test_100_is_not_disarium(self):
        """100 is not Disarium: 1^1 + 0^2 + 0^3 = 1 != 100."""
        assert is_disarium(100) is False

    def test_1000_is_not_disarium(self):
        """1000 is not Disarium: 1^1 + 0^2 + 0^3 + 0^4 = 1 != 1000."""
        assert is_disarium(1000) is False

    def test_99_is_not_disarium(self):
        """99 is not Disarium: 9^1 + 9^2 = 9 + 81 = 90 != 99."""
        assert is_disarium(99) is False

    def test_136_is_not_disarium(self):
        """136 is not Disarium: 1^1 + 3^2 + 6^3 = 1 + 9 + 216 = 226 != 136."""
        assert is_disarium(136) is False


class TestIsDisariumEdgeCases:
    """Tests for edge cases of the is_disarium function."""

    def test_negative_numbers_are_not_disarium(self):
        """All negative numbers are not Disarium."""
        for n in [-1, -89, -175, -598, -1000]:
            assert is_disarium(n) is False, f"{n} should not be Disarium"

    def test_returns_boolean_type(self):
        """is_disarium must return a boolean value."""
        result_true = is_disarium(89)
        result_false = is_disarium(24)
        assert isinstance(result_true, bool)
        assert isinstance(result_false, bool)

    def test_is_exactly_true_for_disarium(self):
        """The return value for Disarium numbers must be exactly True (not 1)."""
        result = is_disarium(175)
        assert result is True
        # Verify it is the strict True singleton
        assert result == 1
        assert result is not 1

    def test_is_exactly_false_for_non_disarium(self):
        """The return value for non-Disarium numbers must be exactly False (not 0)."""
        result = is_disarium(24)
        assert result is False
        assert result == 0
        assert result is not 0


class TestIsDisariumTypeErrors:
    """Tests for type validation of the is_disarium function."""

    def test_rejects_float(self):
        """is_disarium should reject float inputs."""
        with pytest.raises(TypeError):
            is_disarium(1.5)

    def test_rejects_string(self):
        """is_disarium should reject string inputs."""
        with pytest.raises(TypeError):
            is_disarium("175")

    def test_rejects_none(self):
        """is_disarium should reject None input."""
        with pytest.raises(TypeError):
            is_disarium(None)

    def test_rejects_boolean_true(self):
        """is_disarium should reject boolean True (since bool is a subclass of int)."""
        with pytest.raises(TypeError):
            is_disarium(True)

    def test_rejects_boolean_false(self):
        """is_disarium should reject boolean False (since bool is a subclass of int)."""
        with pytest.raises(TypeError):
            is_disarium(False)

    def test_rejects_list(self):
        """is_disarium should reject list input."""
        with pytest.raises(TypeError):
            is_disarium([1, 7, 5])


class TestIsDisariumLargeNumbers:
    """Tests for larger numbers to ensure correctness beyond simple cases."""

    def test_4669_is_not_disarium(self):
        """4669 is not Disarium: 4+216+216+6561 = 6997 != 4669."""
        assert is_disarium(4669) is False

    def test_first_ten_disarium_numbers(self):
        """Verify the first several known Disarium numbers: 0,1,2,3,4,5,6,7,8,9,89,135,175,518,598."""
        disarium_numbers = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 89, 135, 175, 518, 598]
        for n in disarium_numbers:
            assert is_disarium(n) is True, f"{n} should be Disarium"