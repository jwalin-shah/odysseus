"""Tests for the biweight_midvariance function."""
import math

import pytest

from src.stats.biweight_midvariance import biweight_midvariance


def _regular_variance(xs):
    """Plain (population) variance used only for comparison in tests."""
    m = sum(xs) / len(xs)
    return sum((x - m) ** 2 for x in xs) / len(xs)


def test_known_value_simple():
    """Hand-derived value for the integer sequence [1, 2, 3, 4, 5].

    With n=5, M=3, MAD=1 and c=9 the formula reduces to
    5 * sum(w_i * d_i^2) / (sum(w_i)^2 - sum(w_i^2)) which evaluates
    to approximately 2.5354.
    """
    data = [1, 2, 3, 4, 5]
    result = biweight_midvariance(data)
    assert math.isclose(result, 2.5354, rel_tol=1e-3)


def test_robust_to_extreme_outlier():
    """An extreme outlier should not blow up the biweight midvariance,
    while the regular variance explodes."""
    data_clean = [1, 2, 3, 4, 5]
    data_outlier = [1, 2, 3, 4, 5, 1_000_000]

    bw_clean = biweight_midvariance(data_clean)
    bw_outlier = biweight_midvariance(data_outlier)

    var_clean = _regular_variance(data_clean)
    var_outlier = _regular_variance(data_outlier)

    # Sanity: regular variance explodes when an outlier is added.
    assert var_outlier > 1_000_000 * var_clean
    # Biweight midvariance stays within the same order of magnitude.
    assert bw_outlier < 10 * bw_clean


def test_all_equal_returns_zero():
    """All-identical data should yield a zero midvariance."""
    assert biweight_midvariance([5.0, 5.0, 5.0, 5.0, 5.0]) == 0.0
    assert biweight_midvariance([-3.5, -3.5, -3.5]) == 0.0


def test_single_observation_returns_zero():
    """A single value has no dispersion."""
    assert biweight_midvariance([42.0]) == 0.0


def test_empty_raises_value_error():
    with pytest.raises(ValueError):
        biweight_midvariance([])


def test_non_positive_c_raises_value_error():
    with pytest.raises(ValueError):
        biweight_midvariance([1, 2, 3], c=0.0)
    with pytest.raises(ValueError):
        biweight_midvariance([1, 2, 3], c=-2.5)


def test_custom_M_at_median_matches_default():
    """Supplying the sample median as M must reproduce the default output."""
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    # Sample median of an even-length sorted list is the mean of the two
    # middle elements: (5 + 6) / 2 = 5.5.
    assert math.isclose(
        biweight_midvariance(data, M=5.5),
        biweight_midvariance(data),
        rel_tol=1e-12,
    )


def test_custom_M_changes_result():
    """A different location estimate yields a different midvariance."""
    data = [1, 2, 3, 4, 5]
    r1 = biweight_midvariance(data, M=2.0)
    r2 = biweight_midvariance(data, M=4.0)
    assert r1 != r2


def test_accepts_arbitrary_iterables():
    """Generators and tuples must work just as well as lists."""
    data = [1, 2, 3, 4, 5]
    r_gen = biweight_midvariance(x for x in data)
    r_tuple = biweight_midvariance(tuple(data))
    r_list = biweight_midvariance(data)
    assert math.isclose(r_gen, r_list, rel_tol=1e-12)
    assert math.isclose(r_tuple, r_list, rel_tol=1e-12)


def test_positive_for_spread_data():
    """A clearly dispersed symmetric data set must yield a positive value."""
    result = biweight_midvariance([-2, -1, 0, 1, 2])
    assert result > 0.0


def test_c_parameter_changes_result():
    """When a point straddles the cutoff, varying c changes the answer.

    For ``[1, ..., 10, 20]`` the median is 6, MAD is 3.  With c=3 the
    value 20 is rejected (|u| > 1), while with c=15 it is included.
    """
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]
    r_strict = biweight_midvariance(data, c=3.0)
    r_loose = biweight_midvariance(data, c=15.0)
    assert r_strict != r_loose
    assert math.isfinite(r_strict)
    assert math.isfinite(r_loose)


def test_similar_magnitude_to_variance_for_clean_data():
    """For data without outliers the midvariance should be close to
    the regular variance (same order of magnitude)."""
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    bw = biweight_midvariance(data)
    var = _regular_variance(data)
    assert 0.5 * var < bw < 2.0 * var


def test_floats_input():
    """Float inputs (and a mix of ints and floats) are supported."""
    result = biweight_midvariance([0.1, 0.2, 0.3, 0.4, 0.5])
    assert math.isfinite(result)
    assert result > 0.0


def test_zero_outlier_treated_safely():
    """Data with a single huge outlier in the middle must not crash."""
    data = [0.0, 0.0, 0.0, 100.0, 0.0, 0.0, 0.0]
    result = biweight_midvariance(data)
    assert math.isfinite(result)
    assert result >= 0.0