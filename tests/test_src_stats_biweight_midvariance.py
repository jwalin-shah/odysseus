import math
from src.src_stats_biweight_midvariance import src_stats_biweight_midvariance


def test_known_value():
    """Test with a known value computed from the formula.

    For x = [1, 2, ..., 10]:
    - median = 5.5
    - MAD = 2.5
    - c * MAD = 22.5
    - A ≈ 73.427
    - B ≈ 9.046
    - sigma_bw = sqrt(10 * 73.427 / 9.046^2) ≈ 2.995
    """
    x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    result = src_stats_biweight_midvariance(x)
    assert math.isclose(result, 2.995, rel_tol=0.01)


def test_empty_list():
    """Test with empty list returns 0."""
    result = src_stats_biweight_midvariance([])
    assert result == 0.0


def test_single_element():
    """Test with single element returns 0."""
    result = src_stats_biweight_midvariance([5.0])
    assert result == 0.0


def test_all_same():
    """Test with all same values (MAD = 0) returns 0."""
    result = src_stats_biweight_midvariance([5.0, 5.0, 5.0, 5.0])
    assert result == 0.0


def test_with_outliers():
    """Test that the function is robust to outliers."""
    x_clean = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    x_with_outlier = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]

    result_clean = src_stats_biweight_midvariance(x_clean)
    result_with_outlier = src_stats_biweight_midvariance(x_with_outlier)

    # The outlier should not significantly affect the result
    assert abs(result_clean - result_with_outlier) < 1.0


def test_custom_c():
    """Test with custom tuning constant gives different result."""
    x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    result1 = src_stats_biweight_midvariance(x, c=9.0)
    result2 = src_stats_biweight_midvariance(x, c=6.0)
    assert result1 != result2


def test_provided_median():
    """Test with provided median gives same result as computed median."""
    x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    result1 = src_stats_biweight_midvariance(x)
    result2 = src_stats_biweight_midvariance(x, M=5.5)
    assert math.isclose(result1, result2, rel_tol=0.001)


def test_robust_to_extreme_outliers():
    """Test that extreme outliers are masked out."""
    # The outlier 1000 has |u| > 1, so it's masked out
    x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 1000]
    result = src_stats_biweight_midvariance(x)
    assert result > 0
    assert result < 5.0


def test_positive_result():
    """Test that the result is always non-negative."""
    x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    result = src_stats_biweight_midvariance(x)
    assert result >= 0


def test_two_elements():
    """Test with two elements."""
    x = [1.0, 5.0]
    result = src_stats_biweight_midvariance(x)
    assert result > 0
    assert result < 10


def test_negative_values():
    """Test with negative values."""
    x = [-5, -3, -1, 1, 3, 5]
    result = src_stats_biweight_midvariance(x)
    assert result > 0
    assert result < 10


def test_tuple_input():
    """Test that tuple input works the same as list input."""
    x = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    result = src_stats_biweight_midvariance(x)
    assert math.isclose(result, 2.995, rel_tol=0.01)


def test_symmetric_data():
    """Test with symmetric data around zero."""
    x = [-4, -2, -1, 0, 1, 2, 4]
    result = src_stats_biweight_midvariance(x)
    # Median is 0, symmetric data
    assert result > 0
    assert result < 10