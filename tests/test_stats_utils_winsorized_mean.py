"""Tests for stats_utils_winsorized_mean.winsorized_mean."""
import pytest

from src.stats_utils_winsorized_mean import winsorized_mean


class TestWinsorizedMeanBasic:
    def test_simple_sorted_list(self):
        # n=10, limit=0.2, k=int(0.2*10)=2
        # Sorted: [1,2,3,4,5,6,7,8,9,10]
        # replacement_low = sorted[2] = 3
        # replacement_high = sorted[10-2-1] = sorted[7] = 8
        # Winsorized: [3,3,3,4,5,6,7,8,8,8]
        # Sum = 55, mean = 5.5
        assert winsorized_mean([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) == 5.5

    def test_unsorted_input_same_result(self):
        result = winsorized_mean([10, 5, 3, 7, 1, 9, 2, 8, 6, 4])
        assert result == 5.5

    def test_returns_float(self):
        result = winsorized_mean([1.0, 2.0, 3.0])
        assert isinstance(result, float)

    def test_single_value(self):
        assert winsorized_mean([42]) == 42.0

    def test_two_values_no_winsorization(self):
        # n=2, k=int(0.2*2)=0, no winsorization, mean = 5.0
        assert winsorized_mean([3, 7]) == 5.0

    def test_with_negatives(self):
        # Sorted: [-10,-5,0,5,10], n=5, k=int(0.2*5)=1
        # replacement_low = sorted[1] = -5
        # replacement_high = sorted[5-1-1] = sorted[3] = 5
        # Winsorized: [-5,-5,0,5,5], sum = 0, mean = 0
        assert winsorized_mean([-10, -5, 0, 5, 10]) == pytest.approx(0.0)

    def test_custom_limit_zero(self):
        # limit=0 means k=0, regular mean
        data = [1, 2, 3, 4, 5]
        assert winsorized_mean(data, limit=0) == 3.0

    def test_all_same_values(self):
        data = [5, 5, 5, 5, 5]
        assert winsorized_mean(data) == 5.0

    def test_works_with_tuple(self):
        assert winsorized_mean((1, 2, 3, 4, 5, 6, 7, 8, 9, 10)) == 5.5

    def test_floats(self):
        result = winsorized_mean([1.5, 2.5, 3.5, 4.5, 5.5])
        assert result == pytest.approx(3.5)

    def test_limit_one_half(self):
        # n=10, limit=0.5, k=5, every value replaced by center pair
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        result = winsorized_mean(data, limit=0.5)
        # replacement_low = sorted[5] = 6
        # replacement_high = sorted[4] = 5
        # Winsorized: [6,6,6,6,6,5,5,5,5,5], sum = 55, mean = 5.5
        assert result == pytest.approx(5.5)


class TestWinsorizedMeanErrors:
    def test_empty_list_raises_value_error(self):
        with pytest.raises(ValueError):
            winsorized_mean([])

    def test_non_numeric_element_raises_type_error(self):
        with pytest.raises(TypeError):
            winsorized_mean([1, 2, "a", 4])

    def test_none_element_raises_type_error(self):
        with pytest.raises(TypeError):
            winsorized_mean([1, 2, None, 4])

    def test_nan_raises_value_error(self):
        with pytest.raises(ValueError):
            winsorized_mean([1.0, 2.0, float("nan"), 4.0])

    def test_inf_raises_value_error(self):
        with pytest.raises(ValueError):
            winsorized_mean([1.0, 2.0, float("inf"), 4.0])

    def test_string_input_raises_type_error(self):
        with pytest.raises(TypeError):
            winsorized_mean("not a sequence")

    def test_invalid_limit_too_high_raises_value_error(self):
        with pytest.raises(ValueError):
            winsorized_mean([1, 2, 3, 4, 5], limit=0.6)

    def test_negative_limit_raises_value_error(self):
        with pytest.raises(ValueError):
            winsorized_mean([1, 2, 3, 4, 5], limit=-0.1)

    def test_bool_element_raises_type_error(self):
        with pytest.raises(TypeError):
            winsorized_mean([1, 2, True, 4])


class TestWinsorizedMeanProperties:
    def test_winsorized_robust_to_outliers(self):
        # data = [1,2,3,4,5,6,7,8,9,1000]
        # n=10, k=2, replacement_low=3, replacement_high=8
        # Winsorized: [3,3,3,4,5,6,7,8,8,8]
        # Sum = 55, mean = 5.5
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 1000]
        result = winsorized_mean(data)
        assert result == pytest.approx(5.5)
        regular_mean = sum(data) / len(data)
        assert result < regular_mean  # winsorized is pulled toward center

    def test_winsorized_equals_regular_mean_when_no_winsorization(self):
        data = [1, 2, 3, 4, 5]
        regular = sum(data) / len(data)
        assert winsorized_mean(data, limit=0) == pytest.approx(regular)

    def test_asymmetric_data_with_outlier(self):
        # data = [1, 2, 3, 4, 10]
        # n=5, k=1, replacement_low=sorted[1]=2, replacement_high=sorted[3]=4
        # Winsorized: [2,2,3,4,4], sum=15, mean=3.0
        # Regular mean = 4.0
        data = [1, 2, 3, 4, 10]
        result = winsorized_mean(data, limit=0.2)
        assert result == pytest.approx(3.0)
        assert result < sum(data) / len(data)

    def test_symmetric_data_center_preserved(self):
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        assert winsorized_mean(data) == pytest.approx(5.5)