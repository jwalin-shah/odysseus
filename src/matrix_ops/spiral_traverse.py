from typing import List


def spiral_traverse(matrix: List[List[int]]) -> List[int]:
    """
    Traverse a 2D matrix in spiral order (clockwise, starting from top-left).

    Args:
        matrix: A 2D list of integers with m rows and n columns.

    Returns:
        A flat list of all elements visited in spiral order.
    """
    # Handle edge cases: empty matrix or matrix with empty rows
    if not matrix or not matrix[0]:
        return []

    result: List[int] = []
    top, bottom = 0, len(matrix) - 1
    left, right = 0, len(matrix[0]) - 1

    # Continue while there is at least one row and one column to process
    while top <= bottom and left <= right:
        # 1. Move right along the top row
        for col in range(left, right + 1):
            result.append(matrix[top][col])
        top += 1

        # 2. Move down along the right column
        for row in range(top, bottom + 1):
            result.append(matrix[row][right])
        right -= 1

        # 3. Move left along the bottom row (only if rows remain)
        if top <= bottom:
            for col in range(right, left - 1, -1):
                result.append(matrix[bottom][col])
            bottom -= 1

        # 4. Move up along the left column (only if columns remain)
        if left <= right:
            for row in range(bottom, top - 1, -1):
                result.append(matrix[row][left])
            left += 1

    return result