def rotate_90_cw(matrix: list[list]) -> list[list]:
    n = len(matrix)
    # Create a new NxN matrix rotated 90 degrees clockwise
    return [[matrix[n - 1 - j][i] for j in range(n)] for i in range(n)]


def rotate_90_cw_inplace(matrix: list[list]) -> None:
    n = len(matrix)
    # Rotate layer by layer
    for layer in range(n // 2):
        first = layer
        last = n - 1 - layer
        for i in range(first, last):
            offset = i - first
            top = matrix[first][i]
            # left -> top
            matrix[first][i] = matrix[last - offset][first]
            # bottom -> left
            matrix[last - offset][first] = matrix[last][last - offset]
            # right -> bottom
            matrix[last][last - offset] = matrix[i][last]
            # top -> right
            matrix[i][last] = top


def rotate_k(matrix: list[list], k: int) -> list[list]:
    # Normalize k to be in [0, 3]
    k = k % 4
    result = [row[:] for row in matrix]
    for _ in range(k):
        result = rotate_90_cw(result)
    return result