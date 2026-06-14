def spiral_order(matrix: list[list[int]]) -> list[int]:
    """Return all elements in clockwise spiral order starting from top-left."""
    if not matrix or not matrix[0]:
        return []

    result = []
    top, bottom = 0, len(matrix) - 1
    left, right = 0, len(matrix[0]) - 1

    while top <= bottom and left <= right:
        # Traverse from left to right along the top row
        for col in range(left, right + 1):
            result.append(matrix[top][col])
        top += 1

        # Traverse from top to bottom along the right column
        for row in range(top, bottom + 1):
            result.append(matrix[row][right])
        right -= 1

        # Traverse from right to left along the bottom row (if any row remains)
        if top <= bottom:
            for col in range(right, left - 1, -1):
                result.append(matrix[bottom][col])
            bottom -= 1

        # Traverse from bottom to top along the left column (if any column remains)
        if left <= right:
            for row in range(bottom, top - 1, -1):
                result.append(matrix[row][left])
            left += 1

    return result


def generate_spiral(n: int) -> list[list[int]]:
    """Generate an NxN matrix filled with 1..n*n in clockwise spiral order."""
    if n <= 0:
        return []

    matrix = [[0] * n for _ in range(n)]
    top, bottom = 0, n - 1
    left, right = 0, n - 1
    num = 1
    total = n * n

    while num <= total:
        # Fill top row from left to right
        for col in range(left, right + 1):
            matrix[top][col] = num
            num += 1
        top += 1
        if num > total:
            break

        # Fill right column from top to bottom
        for row in range(top, bottom + 1):
            matrix[row][right] = num
            num += 1
        right -= 1
        if num > total:
            break

        # Fill bottom row from right to left
        for col in range(right, left - 1, -1):
            matrix[bottom][col] = num
            num += 1
        bottom -= 1
        if num > total:
            break

        # Fill left column from bottom to top
        for row in range(bottom, top - 1, -1):
            matrix[row][left] = num
            num += 1
        left += 1

    return matrix