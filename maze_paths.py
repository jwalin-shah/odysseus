def maze_paths(maze):
    """Find all paths from the top-left corner to the bottom-right corner.

    The maze is a 2D grid where ``1`` represents an open cell and ``0``
    represents a blocked cell.  A move is only allowed to the right or down.

    Args:
        maze: A 2D list of integers (0/1).

    Returns:
        A list of paths.  Each path is a list of ``(row, col)`` tuples
        starting at ``(0, 0)`` and ending at ``(rows-1, cols-1)``.
        An empty list is returned when no path exists or the input is
        invalid (empty maze, blocked start/end, etc.).
    """
    # Guard against malformed input.
    if not maze or not maze[0]:
        return []

    rows = len(maze)
    cols = len(maze[0])

    # If the start or the destination is blocked, no path is possible.
    if maze[0][0] == 0 or maze[rows - 1][cols - 1] == 0:
        return []

    results = []

    def backtrack(r, c, path):
        # Reached the destination - record a copy of the current path.
        if r == rows - 1 and c == cols - 1:
            results.append(path[:])
            return

        # Try to move down.
        if r + 1 < rows and maze[r + 1][c] == 1:
            path.append((r + 1, c))
            backtrack(r + 1, c, path)
            path.pop()

        # Try to move right.
        if c + 1 < cols and maze[r][c + 1] == 1:
            path.append((r, c + 1))
            backtrack(r, c + 1, path)
            path.pop()

    backtrack(0, 0, [(0, 0)])
    return results