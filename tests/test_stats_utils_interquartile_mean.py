"""Tests for ``stats_utils_interquartile_mean.interquartile_mean``."""
import os
import sys

import pytest

# Make ``src/`` importable regardless of how pytest is invoked.
_SRC_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir, "src")
)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from stats_utils_interquartile_mean import interquartile_mean  # noqa: E402


class TestInterquartileMeanBasic:
    def test_integers_eight_values(self):
        # 1..8, trim 2 from each end -> [3, 4, 5, 6], mean = 4.5
        assert interquartile_mean([1, 2, 3, 4, 5, 6, 7, 8]) == pytest.approx(4.5)

    def test_unsorted_input(self):
        assert interquartile_mean([8, 1, 7, 2, 6, 3, 5, 4]) == pytest.approx(4.5)

    def test_floats(self):
        # Same data as the integer test, expressed as floats.
        assert interquartile_mean(
            [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
        ) == pytest.approx(4.5)

    def test_mixed_int_and_float(self):
        # sorted: [1, 2.5, 3, 4.5, 5, 6.5, 7, 8.5]
        # k = 2, trimmed: [3, 4.5, 5, 6.5]  mean = 4.75
        data = [1, 2.5, 3, 4.5, 5, 6.5, 7, 8.5]
        assert interquartile_mean(data) == pytest.approx(4.75)

    def test_all_same_values(self):
        assert interquartile_mean([7, 7, 7, 7, 7, 7, 7, 7]) == pytest.approx(7.0)

    def test_negative_values(self):
        # -8..-1, trim 2 from each end -> [-6, -5, -4, -3], mean = -4.5
        assert interquartile_mean(
            [-8, -7, -6, -5, -4, -3, -2, -1]
        ) == pytest.approx(-4.5)

    def test_nine_values(self):
        # 1..9, n=9, k=2, trimmed: [3, 4, 5, 6, 7], mean = 5.0
        assert interquartile_mean([1, 2, 3, 4, 5, 6, 7, 8, 9]) == pytest.approx(5.0)

    def test_twelve_values(self):
        # 1..12, n=12, k=3, trimmed: [4..9], mean = 6.5
        assert interquartile_mean(list(range(1, 13))) == pytest.approx(6.5)

    def test_large_dataset(self):
        # 1..100, n=100, k=25, trimmed: 26..75 (1-indexed)
        # sum = (26 + 75) * 50 / 2 = 2525, mean = 50.5
        assert interquartile_mean(list(range(1, 101))) == pytest.approx(50.5)

    def test_returns_float(self):
        result = interquartile_mean([1, 2, 3, 4, 5, 6, 7, 8])
        assert isinstance(result, float)

    def test_does_not_mutate_input(self):
        data = [8, 1, 7, 2, 6, 3, 5, 4]
        snapshot = list(data)
        interquartile_mean(data)
        assert data == snapshot


class TestInterquartileMeanEdgeCases:
    def test_single_value(self):
        assert interquartile_mean([42]) == pytest.approx(42.0)

    def test_two_values(self):
        # n=2, k=0 -> arithmetic mean
        assert interquartile_mean([2, 8]) == pytest.approx(5.0)

    def test_three_values(self):
        # n=3, k=0 -> arithmetic mean
        assert interquartile_mean([1, 5, 9]) == pytest.approx(5.0)

    def test_four_values(self):
        # n=4, k=1 -> middle two values
        assert interquartile_mean([1, 3, 7, 9]) == pytest.approx(5.0)

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            interquartile_mean([])

    def test_none_raises(self):
        with pytest.raises(ValueError):
            interquartile_mean(None)

    def test_accepts_tuple(self):
        assert interquartile_mean((1, 2, 3, 4, 5, 6, 7, 8)) == pytest.approx(4.5)