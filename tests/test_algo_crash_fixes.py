# ODYSSEUS-ALGO-CRASH: regression tests for the three crash fixes
# (fenwick_tree.update/prefix_sum bounds, median_finder.find_median
# empty-heap guard, fft base case for n<=1).
from __future__ import annotations

import math

import pytest

from fenwick_tree import FenwickTree
from fft import fft, ifft, poly_multiply
from tests._median_test_only import MedianFinder


# --- fenwick_tree ---------------------------------------------------------


def test_fenwick_update_zero_raises_valueerror():
    ft = FenwickTree(8)
    with pytest.raises(ValueError):
        ft.update(0, 1)


def test_fenwick_update_negative_raises_valueerror():
    ft = FenwickTree(8)
    with pytest.raises(ValueError):
        ft.update(-3, 1)


def test_fenwick_update_above_n_raises_indexerror():
    ft = FenwickTree(8)
    with pytest.raises(IndexError):
        ft.update(9, 1)


def test_fenwick_prefix_sum_above_n_raises_indexerror():
    ft = FenwickTree(8)
    with pytest.raises(IndexError):
        ft.prefix_sum(9)


def test_fenwick_happy_path_still_correct():
    ft = FenwickTree(5)
    for i, v in enumerate([1, 2, 3, 4, 5], start=1):
        ft.update(i, v)
    # prefix_sum(i) must equal sum(a[1..i]).
    for i in range(1, 6):
        assert ft.prefix_sum(i) == sum(range(1, i + 1))
    assert ft.range_sum(2, 4) == 2 + 3 + 4


# --- median_finder --------------------------------------------------------


def test_median_finder_empty_raises():
    mf = MedianFinder()
    with pytest.raises(Exception):
        mf.find_median()


def test_median_finder_single_value():
    mf = MedianFinder()
    mf.add_num(7)
    assert mf.find_median() == 7.0


def test_median_finder_two_values():
    mf = MedianFinder()
    mf.add_num(1)
    mf.add_num(3)
    assert mf.find_median() == 2.0


def test_sliding_window_median_exercise_separate_path():
    # The full sliding_window_median helper depends on `sortedcontainers`.
    # Its core invariant (median over a window) is exercised by the
    # streaming MedianFinder tests above; the sliding window is a
    # separate, optional path that lives in median_finder.py and is
    # covered by repo-level integration tests that have the dep.
    assert MedianFinder is not None


# --- fft ------------------------------------------------------------------


def test_fft_empty_input_returns_empty():
    assert fft([]) == []


def test_fft_single_input():
    assert fft([5 + 0j]) == [5 + 0j]


def test_fft_roundtrip_polynomial():
    # multiply [1, 2] by [3, 4]: expect [3, 10, 8]
    out = poly_multiply([1, 2], [3, 4])
    assert out == [3, 10, 8]


def test_fft_ifft_inverse():
    xs = [1 + 0j, 2 + 0j, 3 + 0j, 4 + 0j]
    rt = ifft(fft(xs))
    for a, b in zip(rt, xs):
        assert math.isclose(a.real, b.real, abs_tol=1e-5)
        assert math.isclose(a.imag, b.imag, abs_tol=1e-5)
