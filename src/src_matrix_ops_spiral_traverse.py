"""Spiral traversal of a 2D matrix.

This module provides a function to visit the elements of a 2D matrix
in clockwise spiral order, starting from the top-left corner and
working inward.
"""

from __future__ import annotations

from typing import Any, List


def spiral_traverse(matrix: List[List[Any]]) -> List[Any]:
    """Return the elements of ``matrix`` visited in clockwise spiral order.

    The traversal starts at the top-left corner, proceeds right across
    the top row, then down the rightmost column, then left across the
    bottom row, then up the leftmost column, and repeats inward until
    every element has been visited.

    Args:
        matrix: A 2D list (list of rows) representing the matrix. May be
            empty or contain empty rows.

    Returns:
        A flat list of the matrix's elements in spiral order.

    Examples:
        >>> spiral_traverse([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        [1, 2, 3, 6, 9, 8, 7, 4, 5]
        >>> spiral_traverse([])
        []
    """
    if not matrix:
        return []
    if not matrix[0]:
        return []

    result: List[Any] = []
    top, bottom = 0, len(matrix) - 1
    left, right = 0, len(matrix[0]) - 1

    while top <= bottom and left <= right:
        # Traverse from (top, left) -> (top, right)
        for col in range(left, right + 1):
            result.append(matrix[top][col])
        top += 1

        # Traverse from (top, right) -> (bottom, right)
        for row in range(top, bottom + 1):
            result.append(matrix[row][right])
        right -= 1

        # Traverse from (bottom, right) -> (bottom, left)
        # Guard with top <= bottom because the previous vertical pass
        # may have consumed the last remaining row.
        if top <= bottom:
            for col in range(right, left - 1, -1):
                result.append(matrix[bottom][col])
            bottom -= 1

        # Traverse from (bottom, left) -> (top, left)
        # Guard with left <= right because the previous horizontal pass
        # may have consumed the last remaining column.
        if left <= right:
            for row in range(bottom, top - 1, -1):
                result.append(matrix[row][left])
            left += 1

    return result