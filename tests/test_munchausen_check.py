"""Tests for the ``munchausen_check`` function."""
import pytest

from munchausen_check import munchausen_check


# ---------------------------------------------------------------------------
# Known Munchausen numbers
# ---------------------------------------------------------------------------

class TestKnownMunchausenNumbers:
    def test_one_is_munchausen(self):
        # 1 = 1**1
        assert munchausen_check(1) is True

    def test_3435_is_munchausen(self):
        # 3435 = 3**3 + 4**4 + 3**3 + 5**5
        #      = 27  + 256  + 27  + 3125 = 3435
        assert munchausen_check(3435) is True


# ---------------------------------------------------------------------------
# Numbers that are definitely not Munchausen
# ---------------------------------------------------------------------------

class TestNonMunchausenNumbers:
    @pytest.mark.parametrize("n", [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 99, 100, 500])
    def test_small_non_munchausen(self, n):
        assert munchausen_check(n) is False

    def test_values_around_3435(self):
        assert munchausen_check(3434) is False
        assert munchausen_check(3436) is False

    @pytest.mark.parametrize("n", [1000, 2772, 9999, 12345, 99999, 100000])
    def test_larger_non_munchausen(self, n):
        assert munchausen_check(n) is False

    def test_max_digit_power_sum_bound(self):
        # 10 * 9**9 = 3_874_204_890; numbers beyond 10 digits can't match.
        big = 10**11
        assert munchausen_check(big) is False


# ---------------------------------------------------------------------------
# Edge cases and invalid inputs
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_zero_is_not_munchausen(self):
        # The trivial 0^0 case is excluded by convention.
        assert munchausen_check(0) is False

    def test_negative_numbers_are_not_munchausen(self):
        assert munchausen_check(-1) is False
        assert munchausen_check(-3435) is False
        assert munchausen_check(-100) is False

    @pytest.mark.parametrize("value", [1.5, 0.0, 3435.0, "3435", "1", None, [1], (3, 4, 3, 5), {"n": 1}])
    def test_non_integer_inputs_return_false(self, value):
        assert munchausen_check(value) is False

    def test_booleans_are_rejected(self):
        # ``bool`` is a subclass of ``int`` in Python, but we explicitly
        # reject it so True/False aren't silently treated as 1/0.
        assert munchausen_check(True) is False
        assert munchausen_check(False) is False


# ---------------------------------------------------------------------------
# Property-style checks
# ---------------------------------------------------------------------------

class TestProperties:
    def test_result_is_always_boolean(self):
        for n in [-5, -1, 0, 1, 2, 3435, 3434, 999_999]:
            result = munchausen_check(n)
            assert isinstance(result, bool)

    def test_exhaustive_check_up_to_10000(self):
        """Only 1 and 3435 should return True in this range."""
        truthy = [n for n in range(0, 10001) if munchausen_check(n)]
        assert truthy == [1, 3435]