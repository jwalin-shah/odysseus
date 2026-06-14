"""Tests for ``matrix_ops_anti_diag_zigzag``."""

import os
import sys

# Make the ``src/`` directory importable when the tests are executed
# directly (e.g. ``pytest tests/`` from the repository root).
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.normpath(os.path.join(_THIS_DIR, "..", "src"))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from matrix_ops_anti_diag_zigzag import matrix_ops_anti_diag_zigzag  # noqa: E402


def test_3x3_square_matrix():
    matrix = [
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
    ]
    # Anti-diagonals:
    #   d=0: [1]                 -> [1]
    #   d=1: [2, 4]              -> [2, 4]
    #   d=2: [3, 5, 7] reversed  -> [7, 5, 3]
    #   d=3: [6, 8]              -> [6, 8]
    #   d=4: [9] reversed        -> [9]
    expected = [1, 2, 4, 7, 5, 3, 6, 8, 9]
    assert matrix_ops_anti_diag_zigzag(matrix) == expected


def test_1x1_matrix():
    assert matrix_ops_anti_diag_zigzag([[42]]) == [42]


def test_single_row():
    # Every element sits on its own anti-diagonal, so the order is
    # preserved regardless of the zigzag direction.
    assert matrix_ops_anti_diag_zigzag([[1, 2, 3, 4]]) == [1, 2, 3, 4]


def test_single_column():
    # Same as single row: every element is on its own anti-diagonal.
    assert matrix_ops_anti_diag_zigzag([[1], [2], [3], [4]]) == [1, 2, 3, 4]


def test_2x3_matrix():
    matrix = [
        [1, 2, 3],
        [4, 5, 6],
    ]
    # d=0: [1]                 -> [1]
    # d=1: [2, 4]              -> [2, 4]
    # d=2: [3, 5] reversed     -> [5, 3]
    # d=3: [6]                 -> [6]
    expected = [1, 2, 4, 5, 3, 6]
    assert matrix_ops_anti_diag_zigzag(matrix) == expected


def test_3x2_matrix():
    matrix = [
        [1, 2],
        [3, 4],
        [5, 6],
    ]
    # d=0: [1]             -> [1]
    # d=1: [2, 3]          -> [2, 3]
    # d=2: [4, 5] reversed -> [5, 4]
    # d=3: [6]             -> [6]
    expected = [1, 2, 3, 5, 4, 6]
    assert matrix_ops_anti_diag_zigzag(matrix) == expected


def test_3x4_rectangular_matrix():
    matrix = [
        [1,  2,  3,  4],
        [5,  6,  7,  8],
        [9, 10, 11, 12],
    ]
    # d=0: [1]                 -> [1]
    # d=1: [2, 5]              -> [2, 5]
    # d=2: [3, 6, 9] reversed  -> [9, 6, 3]
    # d=3: [4, 7, 10]          -> [4, 7, 10]
    # d=4: [8, 11] reversed    -> [11, 8]
    # d=5: [12]                -> [12]
    expected = [1, 2, 5, 9, 6, 3, 4, 7, 10, 11, 8, 12]
    assert matrix_ops_anti_diag_zigzag(matrix) == expected


def test_empty_matrix():
    assert matrix_ops_anti_diag_zigzag([]) == []


def test_matrix_with_empty_row():
    # A matrix whose only row is empty should also yield an empty list.
    assert matrix_ops_anti_diag_zigzag([[]]) == []


def test_result_length_matches_matrix_size():
    matrix = [
        [1, 2, 3, 4, 5],
        [6, 7, 8, 9, 10],
    ]
    flat = matrix_ops_anti_diag_zigzag(matrix)
    assert len(flat) == 10


def test_result_is_a_permutation_of_matrix_elements():
    matrix = [
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
        [10, 11, 12],
    ]
    flat = matrix_ops_anti_diag_zigzag(matrix)
    expected_elements = [value for row in matrix for value in row]
    assert sorted(flat) == sorted(expected_elements)
    assert len(flat) == len(expected_elements)


def test_works_with_tuples_of_tuples():
    matrix = ((1, 2, 3), (4, 5, 6), (7, 8, 9))
    expected = [1, 2, 4, 7, 5, 3, 6, 8, 9]
    assert matrix_ops_anti_diag_zigzag(matrix) == expected