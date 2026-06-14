"""Zigzag spiral matrix generation.

This module provides a function to generate a matrix filled in a
zigzag spiral pattern, starting from the top-left corner and spiraling
inward in a clockwise direction. The traversal path zigzags (turns) as
it follows the boundaries of the ever-shrinking inner rectangle.
"""


def zigzag_spiral(rows, cols):
    """Generate a matrix filled in a zigzag spiral pattern.

    Starting from the top-left corner, the matrix is filled with
    consecutive integers (1, 2, 3, ...) following a clockwise spiral
    path inward. The path creates a zigzag-like visual pattern as it
    turns at each boundary.

    Args:
        rows: Number of rows. Must be a non-negative integer.
        cols: Number of columns. Must be a non-negative integer.

    Returns:
        A 2D list (matrix) of size rows x cols filled with integers
        from 1 to rows * cols in spiral order. Returns an empty list
        if rows or cols is 0.

    Raises:
        TypeError: If rows or cols is not an integer.
        ValueError: If rows or cols is negative.

    Examples:
        >>> zigzag_spiral(3, 3)
        [[1, 2, 3], [8, 9, 4], [7, 6, 5]]

        >>> zigzag_spiral(2, 2)
        [[1, 2], [4, 3]]

        >>> zigzag_spiral(1, 4)
        [[1, 2, 3, 4]]
    """
    # --- input validation -------------------------------------------------
    # Reject booleans explicitly because bool is a subclass of int in Python.
    if not isinstance(rows, int) or isinstance(rows, bool):
        raise TypeError("rows must be an integer")
    if not isinstance(cols, int) or isinstance(cols, bool):
        raise TypeError("cols must be an integer")
    if rows < 0 or cols < 0:
        raise ValueError("rows and cols must be non-negative")
    if rows == 0 or cols == 0:
        return []

    # --- build the spiral --------------------------------------------------
    matrix = [[0] * cols for _ in range(rows)]
    num = 1
    top, bottom = 0, rows - 1
    left, right = 0, cols - 1

    while top <= bottom and left <= right:
        # 1) left -> right along the current top row
        for j in range(left, right + 1):
            matrix[top][j] = num
            num += 1
        top += 1

        # 2) top -> bottom along the current right column
        for i in range(top, bottom + 1):
            matrix[i][right] = num
            num += 1
        right -= 1

        # 3) right -> left along the current bottom row (if any rows remain)
        if top <= bottom:
            for j in range(right, left - 1, -1):
                matrix[bottom][j] = num
                num += 1
            bottom -= 1

        # 4) bottom -> top along the current left column (if any cols remain)
        if left <= right:
            for i in range(bottom, top - 1, -1):
                matrix[i][left] = num
                num += 1
            left += 1

    return matrix