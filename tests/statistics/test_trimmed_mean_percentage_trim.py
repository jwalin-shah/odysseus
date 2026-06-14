import os
import sys
import importlib.util
import pytest

# Load the implementation module directly from its file path. This avoids the
# name collision with the Python standard library's ``statistics`` module so
# the local ``statistics`` package is not required to be a proper package
# for these tests to import the function under test.
_impl_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "statistics", "trimmed_mean_percentage_trim.py",
)
_impl_path = os.path.abspath(_impl_path)
_spec = importlib.util.spec_from_file_location(
    "trimmed_mean_percentage_trim_impl", _impl_path
)
_impl_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_impl_module)

trimmed_mean_percentage_trim = _impl_module.trimmed_mean_percentage_trim


def test_trimmed_mean_10_percent():
    # 10 elements, 10% trim => drop 1 from each end of [1..10].
    data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    # Remaining: [2,3,4,5,6,7,8,9]; mean = 44/8 = 5.5
    assert trimmed_mean_percentage_trim(data, 10) == 5.5


def test_trimmed_mean_0_percent_is_regular_mean():
    data = [1, 2, 3, 4, 5]
    assert trimmed_mean_percentage_trim(data, 0) == 3.0


def test_trimmed_mean_25_percent():
    data = [1, 2, 3, 4, 5, 6, 7, 8]
    # 25% of 8 = 2; drop 2 from each end: [3, 4, 5, 6]; mean = 4.5
    assert trimmed_mean_percentage_trim(data, 25) == 4.5


def test_trimmed_mean_with_floats():
    data = [1.5, 2.5, 3.5, 4.5, 5.5]
    # 20% of 5 = 1; drop 1 from each end: [2.5, 3.5, 4.5]; mean = 3.5
    assert trimmed_mean_percentage_trim(data, 20) == pytest.approx(3.5)


def test_trimmed_mean_handles_unsorted_input():
    data = [5, 1, 3, 2, 4]
    # Sorted: [1, 2, 3, 4, 5]; 20% trim => [2, 3, 4]; mean = 3.0
    assert trimmed_mean_percentage_trim(data, 20) == 3.0


def test_trimmed_mean_small_percentage_trims_nothing():
    # 10% of 3 = 0.3 -> int -> 0, so nothing is trimmed.
    data = [10, 20, 30]
    assert trimmed_mean_percentage_trim(data, 10) == 20.0


def test_trimmed_mean_invalid_percentage_too_large():
    with pytest.raises(ValueError):
        trimmed_mean_percentage_trim([1, 2, 3, 4], 50)


def test_trimmed_mean_invalid_percentage_negative():
    with pytest.raises(ValueError):
        trimmed_mean_percentage_trim([1, 2, 3, 4], -1)


def test_trimmed_mean_empty_data_raises():
    with pytest.raises(ValueError):
        trimmed_mean_percentage_trim([], 10)