"""Tests for the zigzag_spiral module."""
import os
import sys

# Allow running the tests from the repo root or from the tests/ directory
# by ensuring the project root is on sys.path.
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import pytest

from zigzag_spiral import zigzag_spiral


# ---------------------------------------------------------------------------
# Shape and value invariants
# ---------------------------------------------------------------------------


def test_matrix_dimensions():
    """The returned matrix must have the requested (rows, cols) shape."""
    rows, cols = 5, 7
    result = zigzag_spiral(rows, cols)
    assert len(result) == rows
    assert all(len(row) == cols for row in result)


def test_contains_every_integer_exactly_once():
    """The spiral should contain 1..rows*cols each exactly once."""
    rows, cols = 4, 5
    result = zigzag_spiral(rows, cols)
    flat = [value for row in result for value in row]
    assert sorted(flat) == list(range(1, rows * cols + 1))


def test_total_count_matches_dimensions():
    """The number of cells should equal rows * cols."""
    result = zigzag_spiral(6, 3)
    assert sum(len(row) for row in result) == 6 * 3


# ---------------------------------------------------------------------------
# Specific known outputs
# ---------------------------------------------------------------------------


def test_3x3_spiral():
    """3x3 should produce the classic clockwise spiral."""
    result = zigzag_spiral(3, 3)
    expected = [
        [1, 2, 3],
        [8, 9, 4],
        [7, 6, 5],
    ]
    assert result == expected


def test_2x2_spiral():
    """2x2 should produce a small clockwise spiral."""
    result = zigzag_spiral(2, 2)
    expected = [
        [1, 2],
        [4, 3],
    ]
    assert result == expected


def test_4x4_spiral():
    """4x4 should produce a multi-ring clockwise spiral."""
    result = zigzag_spiral(4, 4)
    expected = [
        [1,  2,  3,  4],
        [12, 13, 14, 5],
        [11, 16, 15, 6],
        [10, 9,  8,  7],
    ]
    assert result == expected


def test_2x3_spiral():
    """2x3 should produce the correct short spiral."""
    result = zigzag_spiral(2, 3)
    expected = [
        [1, 2, 3],
        [6, 5, 4],
    ]
    assert result == expected


def test_3x2_spiral():
    """3x2 (taller than wide) should still spiral correctly."""
    result = zigzag_spiral(3, 2)
    expected = [
        [1, 2],
        [6, 3],
        [5, 4],
    ]
    assert result == expected


def test_5x5_spiral():
    """5x5 should spiral with multiple rings."""
    result = zigzag_spiral(5, 5)
    expected = [
        [1,  2,  3,  4,  5],
        [16, 17, 18, 19, 6],
        [15, 24, 25, 20, 7],
        [14, 23, 22, 21, 8],
        [13, 12, 11, 10, 9],
    ]
    assert result == expected


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_1x1_matrix():
    """A 1x1 matrix should just contain 1."""
    assert zigzag_spiral(1, 1) == [[1]]


def test_1xN_row():
    """A single row should fill left to right."""
    assert zigzag_spiral(1, 5) == [[1, 2, 3, 4, 5]]


def test_Nx1_column():
    """A single column should fill top to bottom."""
    assert zigzag_spiral(5, 1) == [[1], [2], [3], [4], [5]]


def test_zero_rows_returns_empty_list():
    """Zero rows should return an empty list."""
    assert zigzag_spiral(0, 3) == []


def test_zero_cols_returns_empty_list():
    """Zero columns should return an empty list."""
    assert zigzag_spiral(3, 0) == []


def test_both_zero_returns_empty_list():
    """Both zero should return an empty list."""
    assert zigzag_spiral(0, 0) == []


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_negative_rows_raises_value_error():
    """Negative row count should raise ValueError."""
    with pytest.raises(ValueError):
        zigzag_spiral(-1, 3)


def test_negative_cols_raises_value_error():
    """Negative column count should raise ValueError."""
    with pytest.raises(ValueError):
        zigzag_spiral(3, -1)


def test_float_rows_raises_type_error():
    """A non-integer row count should raise TypeError."""
    with pytest.raises(TypeError):
        zigzag_spiral(3.5, 3)


def test_string_input_raises_type_error():
    """A string input should raise TypeError."""
    with pytest.raises(TypeError):
        zigzag_spiral("3", 3)


def test_none_input_raises_type_error():
    """None input should raise TypeError."""
    with pytest.raises(TypeError):
        zigzag_spiral(None, 3)