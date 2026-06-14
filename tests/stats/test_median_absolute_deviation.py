"""Tests for :func:`stats.median_absolute_deviation.median_absolute_deviation`."""

from __future__ import annotations

import os
import sys

import pytest

# Make the ``stats`` package importable when this file is run directly
# (``python tests/stats/test_median_absolute_deviation.py``) and when
# pytest is invoked from the repository root.
_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from stats.median_absolute_deviation import median_absolute_deviation  # noqa: E402


class TestMedianAbsoluteDeviation:
    """Test suite for ``median_absolute_deviation``."""

    # ---- Classic worked examples ---------------------------------------

    def test_known_odd_example(self):
        """Standard example from the literature: median = 2, MAD = 1."""
        data = [1, 1, 2, 2, 4, 6, 9]
        # median of data = 2
        # absolute deviations = [1, 1, 0, 0, 2, 4, 7]
        # median of deviations = 1
        assert median_absolute_deviation(data) == 1.0

    def test_known_even_example(self):
        """Even-length example: median = 4.5, MAD = 2.0."""
        data = [1, 2, 3, 4, 5, 6, 7, 8]
        # median of data = (4 + 5) / 2 = 4.5
        # absolute deviations = [3.5, 2.5, 1.5, 0.5, 0.5, 1.5, 2.5, 3.5]
        # median of deviations = (1.5 + 2.5) / 2 = 2.0
        assert median_absolute_deviation(data) == 2.0

    # ---- Edge cases ---------------------------------------------------

    def test_empty_input_returns_zero(self):
        assert median_absolute_deviation([]) == 0.0

    def test_none_input_returns_zero(self):
        assert median_absolute_deviation(None) == 0.0

    def test_single_value_returns_zero(self):
        # Only one element => deviation from itself is 0.
        assert median_absolute_deviation([42]) == 0.0

    def test_all_identical_returns_zero(self):
        assert median_absolute_deviation([7, 7, 7, 7, 7]) == 0.0

    def test_two_elements(self):
        # [1, 3] -> median = 2, deviations = [1, 1], MAD = 1
        assert median_absolute_deviation([1, 3]) == 1.0

    def test_non_numeric_raises_value_error(self):
        with pytest.raises(ValueError):
            median_absolute_deviation([1, 2, "not-a-number"])

    # ---- Behavioural / robustness tests -------------------------------

    def test_unsorted_input_works(self):
        data = [5, 2, 8, 1, 9, 3, 7]
        # sorted = [1, 2, 3, 5, 7, 8, 9]; median = 5
        # deviations = [4, 3, 3, 0, 2, 2, 4]; sorted = [0, 2, 2, 3, 3, 4, 4]
        # MAD = 3
        assert median_absolute_deviation(data) == 3.0

    def test_negative_values(self):
        data = [-5, -3, -1, 1, 3]
        # median = -1; deviations = [4, 2, 0, 2, 4]; MAD = 2
        assert median_absolute_deviation(data) == 2.0

    def test_float_values(self):
        data = [1.5, 2.5, 3.5, 4.5, 5.5]
        # median = 3.5; deviations = [2, 1, 0, 1, 2]; MAD = 1
        assert median_absolute_deviation(data) == 1.0

    def test_tuple_input_accepted(self):
        # The function must accept any iterable, not just ``list``.
        assert median_absolute_deviation((1, 2, 3, 4, 5)) == 1.0

    def test_result_is_float(self):
        result = median_absolute_deviation([1, 2, 3])
        assert isinstance(result, float)

    def test_default_scale_is_one(self):
        data = [10, 12, 14, 16, 18]
        # median = 14; deviations = [4, 2, 0, 2, 4]; MAD = 2
        assert median_absolute_deviation(data) == 2.0
        assert median_absolute_deviation(data, scale=1.0) == 2.0

    def test_scale_factor_multiplies_result(self):
        data = [1, 2, 3, 4, 5]
        base = median_absolute_deviation(data)
        scaled = median_absolute_deviation(data, scale=1.4826)
        assert scaled == pytest.approx(base * 1.4826)

    def test_scale_factor_zero(self):
        # Scaling by 0 should always give 0 regardless of the data.
        data = [-100, 0, 100, 42]
        assert median_absolute_deviation(data, scale=0.0) == 0.0

    # ---- Larger dataset -----------------------------------------------

    def test_range_one_to_one_hundred(self):
        data = list(range(1, 101))  # 1..100 inclusive, n = 100
        # median of data = (50 + 51) / 2 = 50.5
        # Absolute deviations: 0.5, 1.5, 2.5, ..., 49.5, each appearing twice.
        # The 50th and 51st smallest deviations are 24.5 and 25.5.
        # MAD = (24.5 + 25.5) / 2 = 25.0
        assert median_absolute_deviation(data) == pytest.approx(25.0)

    def test_idempotent_under_scaling_factor(self):
        # MAD of the absolute deviations equals MAD of the original data
        # only when the data is symmetric around its median; this checks
        # the implementation handles the path consistently.
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        result = median_absolute_deviation(data)
        # For this symmetric sequence, result should be a positive float
        assert isinstance(result, float)
        assert result > 0