def anti_diag_zigzag(matrix):
    """
    Traverse a matrix in anti-diagonal zigzag order.

    Elements are collected along anti-diagonals (where i + j is constant).
    The traversal direction alternates: anti-diagonals with even sum are
    traversed from top to bottom (increasing row index), and those with
    odd sum are traversed from bottom to top (decreasing row index).

    Args:
        matrix: A 2D list (list of lists) representing the matrix.
                May be empty or contain empty rows.

    Returns:
        A flat list of all elements in anti-diagonal zigzag order.
    """
    # Edge cases: empty matrix or matrix with empty rows
    if not matrix:
        return []
    if not matrix[0]:
        return []

    m = len(matrix)
    n = len(matrix[0])

    result = []
    # There are m + n - 1 anti-diagonals, with sums from 0 to m + n - 2
    for s in range(m + n - 1):
        diagonal = []
        # For a given sum s, valid i must satisfy:
        #   0 <= i < m  and  0 <= s - i < n
        # => max(0, s - n + 1) <= i <= min(s, m - 1)
        i_start = max(0, s - n + 1)
        i_end = min(s, m - 1)

        for i in range(i_start, i_end + 1):
            j = s - i
            diagonal.append(matrix[i][j])

        # Reverse every other anti-diagonal to create the zigzag pattern.
        if s % 2 == 1:
            diagonal.reverse()

        result.extend(diagonal)

    return result