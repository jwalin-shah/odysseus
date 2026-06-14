"""Pure-Python matrix operations.

This module provides a small set of linear-algebra primitives operating on
matrices represented as lists (or tuples) of lists (or tuples) of numbers.
It intentionally avoids any external dependencies (e.e. NumPy) so it can be
used in minimal environments.

Conventions
-----------
* A matrix is a rectangular 2-D structure: a list of rows, where every row
  is a list of numbers and all rows have the same length.
* The shape of an ``m x n`` matrix is the pair ``(m, n)``.
* The ``0 x 0`` matrix is the empty list ``[]``; its determinant is defined
  to be ``1`` by convention.
"""

from __future__ import annotations

from typing import Any, List, Tuple, Union

Number = Union[int, float]
Matrix = List[List[Number]]

__all__ = [
    "MatrixError",
    "shape",
    "is_square",
    "add",
    "subtract",
    "scalar_multiply",
    "multiply",
    "transpose",
    "determinant",
    "inverse",
    "trace",
    "identity",
]


class MatrixError(ValueError):
    """Raised when a matrix operation cannot be performed."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _validate(matrix: Any) -> Tuple[int, int]:
    """Return ``(rows, cols)`` for *matrix* after validating its structure.

    Raises
    ------
    MatrixError
        If *matrix* is not a list/tuple of equally-sized, non-empty lists.
    """
    if not isinstance(matrix, (list, tuple)):
        raise MatrixError("Matrix must be a list of lists")
    rows = len(matrix)
    if rows == 0:
        return (0, 0)
    cols: int = 0
    for r, row in enumerate(matrix):
        if not isinstance(row, (list, tuple)):
            raise MatrixError(f"Row {r} is not a list")
        if r == 0:
            cols = len(row)
            if cols == 0:
                raise MatrixError("Matrix rows must be non-empty")
        elif len(row) != cols:
            raise MatrixError(
                f"Inconsistent row lengths: row 0 has {cols}, "
                f"row {r} has {len(row)}"
            )
    return (rows, cols)


# ---------------------------------------------------------------------------
# Shape utilities
# ---------------------------------------------------------------------------


def shape(matrix: Matrix) -> Tuple[int, int]:
    """Return the ``(rows, cols)`` shape of *matrix*."""
    return _validate(matrix)


def is_square(matrix: Matrix) -> bool:
    """Return ``True`` if *matrix* is square (``rows == cols``)."""
    rows, cols = _validate(matrix)
    return rows == cols


# ---------------------------------------------------------------------------
# Element-wise operations
# ---------------------------------------------------------------------------


def add(a: Matrix, b: Matrix) -> Matrix:
    """Element-wise matrix addition: return ``a + b``."""
    sa = _validate(a)
    sb = _validate(b)
    if sa != sb:
        raise MatrixError(f"Shape mismatch for add: {sa} vs {sb}")
    return [[a[i][j] + b[i][j] for j in range(sa[1])] for i in range(sa[0])]


def subtract(a: Matrix, b: Matrix) -> Matrix:
    """Element-wise matrix subtraction: return ``a - b``."""
    sa = _validate(a)
    sb = _validate(b)
    if sa != sb:
        raise MatrixError(f"Shape mismatch for subtract: {sa} vs {sb}")
    return [[a[i][j] - b[i][j] for j in range(sa[1])] for i in range(sa[0])]


def scalar_multiply(a: Matrix, scalar: Number) -> Matrix:
    """Return *scalar* times *a* (element-wise)."""
    sa = _validate(a)
    return [[a[i][j] * scalar for j in range(sa[1])] for i in range(sa[0])]


# ---------------------------------------------------------------------------
# Matrix multiplication
# ---------------------------------------------------------------------------


def multiply(a: Matrix, b: Matrix) -> Matrix:
    """Return the matrix product ``a @ b``."""
    sa = _validate(a)
    sb = _validate(b)
    if sa[1] != sb[0]:
        raise MatrixError(
            f"Shape mismatch for multiply: inner dimensions "
            f"{sa[1]} and {sb[0]}"
        )
    rows, cols, inner = sa[0], sb[1], sa[1]
    result: Matrix = [[0] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            total: Number = 0
            for k in range(inner):
                total += a[i][k] * b[k][j]
            result[i][j] = total
    return result


# ---------------------------------------------------------------------------
# Transpose
# ---------------------------------------------------------------------------


def transpose(a: Matrix) -> Matrix:
    """Return the transpose of *a*."""
    sa = _validate(a)
    if sa == (0, 0):
        return []
    return [[a[i][j] for i in range(sa[0])] for j in range(sa[1])]


# ---------------------------------------------------------------------------
# Determinant
# ---------------------------------------------------------------------------


def determinant(a: Matrix) -> Number:
    """Compute the determinant of a square matrix via Laplace expansion.

    The ``0 x 0`` matrix has determinant ``1`` by convention.
    """
    sa = _validate(a)
    if sa[0] != sa[1]:
        raise MatrixError(f"Determinant requires a square matrix, got {sa}")
    n = sa[0]
    if n == 0:
        return 1
    if n == 1:
        return a[0][0]
    if n == 2:
        return a[0][0] * a[1][1] - a[0][1] * a[1][0]
    det: Number = 0
    for j in range(n):
        minor = [row[:j] + row[j + 1:] for row in a[1:]]
        det += ((-1) ** j) * a[0][j] * determinant(minor)
    return det


# ---------------------------------------------------------------------------
# Inverse (Gauss-Jordan elimination)
# ---------------------------------------------------------------------------


def inverse(a: Matrix) -> Matrix:
    """Return the inverse of a square, invertible matrix.

    Uses Gauss-Jordan elimination with partial pivoting on the augmented
    matrix ``[A | I]``. The result is always a matrix of floats.
    """
    sa = _validate(a)
    if sa[0] != sa[1]:
        raise MatrixError(f"Inverse requires a square matrix, got {sa}")
    n = sa[0]
    if n == 0:
        raise MatrixError("Cannot invert a 0x0 matrix")
    # Build the augmented matrix [A | I] using floats so we can divide.
    aug: List[List[float]] = []
    for i, row in enumerate(a):
        new_row = [float(v) for v in row]
        for j in range(n):
            new_row.append(1.0 if i == j else 0.0)
        aug.append(new_row)
    # Gauss-Jordan elimination with partial pivoting.
    for i in range(n):
        pivot_row = i
        if aug[i][i] == 0:
            for k in range(i + 1, n):
                if aug[k][i] != 0:
                    pivot_row = k
                    break
            else:
                raise MatrixError("Matrix is singular; inverse does not exist")
            aug[i], aug[pivot_row] = aug[pivot_row], aug[i]
        pivot = aug[i][i]
        inv_pivot = 1.0 / pivot
        # Scale the pivot row so the leading entry becomes 1.
        for j in range(2 * n):
            aug[i][j] *= inv_pivot
        # Eliminate the pivot column from every other row.
        for k in range(n):
            if k == i:
                continue
            factor = aug[k][i]
            if factor == 0:
                continue
            for j in range(2 * n):
                aug[k][j] -= factor * aug[i][j]
    return [row[n:] for row in aug]


# ---------------------------------------------------------------------------
# Trace and identity
# ---------------------------------------------------------------------------


def trace(a: Matrix) -> Number:
    """Return the trace of a square matrix (sum of diagonal entries)."""
    sa = _validate(a)
    if sa[0] != sa[1]:
        raise MatrixError(f"Trace requires a square matrix, got {sa}")
    return sum(a[i][i] for i in range(sa[0]))


def identity(n: int) -> Matrix:
    """Return the ``n x n`` identity matrix."""
    if not isinstance(n, int) or n < 0:
        raise MatrixError("Identity size must be a non-negative integer")
    return [[1 if i == j else 0 for j in range(n)] for i in range(n)]