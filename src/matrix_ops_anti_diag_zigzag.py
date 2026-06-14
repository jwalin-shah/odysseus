"""Matrix operations: anti-diagonal zigzag traversal.

This module exposes :func:`matrix_ops_anti_diag_zigzag` which flattens a
2-D matrix by walking it anti-diagonal by anti-diagonal while alternating
the traversal direction at every step (a "zigzag" pattern).

The anti-diagonals are defined by the constant ``i + j``.  Within each
anti-diagonal:

* For an even diagonal index ``d`` the elements are emitted from the
  bottom-left end (largest row index) up to the top-right end.
* For an odd diagonal index ``d`` the elements are emitted from the
  top-right end (smallest row index) down to the bottom-left end.
"""

from __future__ import annotations

from typing import Any, List, Sequence


def matrix_ops_anti_diag_zigzag(matrix: Sequence[Sequence[Any]]) -> List[Any]:
    """Return ``matrix`` flattened in anti-diagonal zigzag order.

    Parameters
    ----------
    matrix:
        A 2-D sequence (e.g. list of lists, tuple of tuples).  Each row
        must have the same length, although the function tolerates
        empty input.  Elements may be of any type.

    Returns
    -------
    list
        A new flat list containing every element of ``matrix`` exactly
        once, ordered by the anti-diagonal zigzag traversal described
        in the module docstring.

    Examples
    --------
    >>> matrix_ops_anti_diag_zigzag([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
    [1, 2, 4, 7, 5, 3, 6, 8, 9]

    >>> matrix_ops_anti_diag_zigzag([])
    []
    """
    # Guard against empty / malformed input.
    if not matrix:
        return []
    rows = len(matrix)
    first_row = matrix[0] if rows > 0 else []
    cols = len(first_row)
    if cols == 0:
        return []

    result: List[Any] = []
    # The anti-diagonals are indexed by d = i + j, ranging from
    # 0 (top-left corner) up to (rows - 1) + (cols - 1) (bottom-right).
    for d in range(rows + cols - 1):
        diagonal: List[Any] = []
        i_start = max(0, d - cols + 1)
        i_end = min(rows - 1, d)
        for i in range(i_start, i_end + 1):
            j = d - i
            diagonal.append(matrix[i][j])
        # Zigzag: even anti-diagonals are emitted bottom-to-top.
        if d % 2 == 0:
            diagonal.reverse()
        result.extend(diagonal)
    return result


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    demo = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12],
    ]
    print(matrix_ops_anti_diag_zigzag(demo))