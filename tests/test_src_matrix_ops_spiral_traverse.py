"""Tests for ``src.src_matrix_ops_spiral_traverse.spiral_traverse``."""

import os
import sys

# Make the ``src/`` directory importable regardless of where pytest is
# invoked from.
_SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

from src_matrix_ops_spiral_traverse import spiral_traverse  # noqa: E402


class TestSpiralTraverse:
    """Behavioral tests for ``spiral_traverse``."""

    def test_3x3_square_matrix(self):
        matrix = [
            [1, 2, 3],
            [4, 5, 6],
            [7, 8, 9],
        ]
        assert spiral_traverse(matrix) == [1, 2, 3, 6, 9, 8, 7, 4, 5]

    def test_2x2_matrix(self):
        matrix = [
            [1, 2],
            [3, 4],
        ]
        assert spiral_traverse(matrix) == [1, 2, 4, 3]

    def test_5x5_square_matrix(self):
        matrix = [
            [1, 2, 3, 4, 5],
            [6, 7, 8, 9, 10],
            [11, 12, 13, 14, 15],
            [16, 17, 18, 19, 20],
            [21, 22, 23, 24, 25],
        ]
        expected = [
            1, 2, 3, 4, 5,
            10, 15, 20, 25,
            24, 23, 22, 21,
            16, 11, 6,
            7, 8, 9,
            14, 19,
            18, 17,
            12,
            13,
        ]
        assert spiral_traverse(matrix) == expected

    def test_rectangular_more_rows_than_columns(self):
        matrix = [
            [1, 2, 3],
            [4, 5, 6],
            [7, 8, 9],
            [10, 11, 12],
        ]
        assert spiral_traverse(matrix) == [
            1, 2, 3,
            6, 9, 12,
            11, 10, 7,
            4,
            5, 8,
        ]

    def test_rectangular_more_columns_than_rows(self):
        matrix = [
            [1, 2, 3, 4],
            [5, 6, 7, 8],
            [9, 10, 11, 12],
        ]
        assert spiral_traverse(matrix) == [
            1, 2, 3, 4,
            8, 12,
            11, 10, 9,
            5,
            6, 7,
        ]

    def test_single_row(self):
        assert spiral_traverse([[1, 2, 3, 4, 5]]) == [1, 2, 3, 4, 5]

    def test_single_column(self):
        assert spiral_traverse([[1], [2], [3], [4], [5]]) == [1, 2, 3, 4, 5]

    def test_single_element(self):
        assert spiral_traverse([[42]]) == [42]

    def test_empty_matrix(self):
        assert spiral_traverse([]) == []

    def test_matrix_with_empty_rows(self):
        assert spiral_traverse([[]]) == []

    def test_returns_a_list(self):
        result = spiral_traverse([[1, 2], [3, 4]])
        assert isinstance(result, list)

    def test_preserves_element_values(self):
        # String and mixed-type values should pass through unchanged.
        matrix = [
            ["a", "b", "c"],
            ["d", "e", "f"],
            ["g", "h", "i"],
        ]
        assert spiral_traverse(matrix) == [
            "a", "b", "c", "f", "i", "h", "g", "d", "e",
        ]