"""Tests for ds-segment-tree implementation.

Covers SegmentTree(arr) with range sum query and point update.
"""
import sys
import os
import pytest

# Add repo root to path so we can import segment_tree module directly.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from segment_tree import SegmentTree


def test_basic_range_sum():
    arr = [1, 3, 5, 7, 9, 11]
    st = SegmentTree(arr)
    assert st.query(0, 5) == 36
    assert st.query(0, 0) == 1
    assert st.query(2, 4) == 21
    assert st.query(1, 3) == 15


def test_single_element_array():
    arr = [42]
    st = SegmentTree(arr)
    assert st.query(0, 0) == 42


def test_empty_array():
    arr = []
    st = SegmentTree(arr)
    # Query on empty tree should return 0 (neutral element for sum).
    assert st.query(0, 0) == 0


def test_update_changes_future_queries():
    arr = [2, 4, 6, 8]
    st = SegmentTree(arr)
    assert st.query(0, 3) == 20
    st.update(1, 10)
    assert st.query(0, 3) == 26
    assert st.query(0, 0) == 2
    assert st.query(1, 1) == 10
    assert st.query(2, 3) == 14


def test_update_to_zero():
    arr = [5, 5, 5, 5]
    st = SegmentTree(arr)
    assert st.query(0, 3) == 20
    st.update(0, 0)
    assert st.query(0, 3) == 15
    assert st.query(0, 0) == 0


def test_all_same_values():
    arr = [7] * 10
    st = SegmentTree(arr)
    assert st.query(0, 9) == 70
    assert st.query(3, 6) == 28
    st.update(5, 3)
    assert st.query(0, 9) == 66
    assert st.query(3, 6) == 24


def test_negative_values():
    arr = [-1, -2, -3, -4, -5]
    st = SegmentTree(arr)
    assert st.query(0, 4) == -15
    assert st.query(1, 3) == -9
    st.update(2, 10)
    assert st.query(0, 4) == -2
    assert st.query(1, 3) == 4


def test_query_full_range_multiple_updates():
    arr = [1, 2, 3, 4, 5]
    st = SegmentTree(arr)
    st.update(0, 100)
    st.update(4, -50)
    assert st.query(0, 4) == 100 + 2 + 3 + 4 + (-50)
    assert st.query(0, 0) == 100
    assert st.query(4, 4) == -50


def test_query_returns_int_type():
    arr = [1, 2, 3]
    st = SegmentTree(arr)
    result = st.query(0, 2)
    assert isinstance(result, int)
    assert result == 6


def test_two_element_array():
    arr = [10, 20]
    st = SegmentTree(arr)
    assert st.query(0, 1) == 30
    assert st.query(0, 0) == 10
    assert st.query(1, 1) == 20
    st.update(0, 5)
    st.update(1, 15)
    assert st.query(0, 1) == 20