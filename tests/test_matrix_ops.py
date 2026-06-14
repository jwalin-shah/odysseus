"""Tests for the ``matrix_ops`` module."""

import os
import sys

import pytest

# Make the package importable when running pytest from the repo root without
# a conftest.py at the root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from matrix_ops import (  # noqa: E402
    MatrixError,
    add,
    determinant,
    identity,
    inverse,
    is_square,
    multiply,
    scalar_multiply,
    shape,
    subtract,
    trace,
    transpose,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _approx_equal(actual, expected, tol=1e-9):
    """Assert that *actual* and *expected* matrices are equal up to *tol*."""
    rows_a = len(actual)
    cols_a = len(actual[0]) if rows_a else 0
    rows_e = len(expected)
    cols_e = len(expected[0]) if rows_e else 0
    assert (rows_a, cols_a) == (rows_e, cols_e), (
        f"Shape mismatch: {(rows_a, cols_a)} vs {(rows_e, cols_e)}"
    )
    for r in range(rows_a):
        for c in range(cols_a):
            assert abs(actual[r][c] - expected[r][c]) < tol, (
                f"Element ({r}, {c}) differs: {actual[r][c]} vs {expected[r][c]}"
            )


# ---------------------------------------------------------------------------
# shape / is_square / validation
# ---------------------------------------------------------------------------


def test_shape_square():
    assert shape([[1, 2], [3, 4]]) == (2, 2)


def test_shape_rectangular():
    assert shape([[1, 2, 3], [4, 5, 6]]) == (2, 3)


def test_shape_empty_matrix():
    assert shape([]) == (0, 0)


def test_is_square_true():
    assert is_square([[1, 2], [3, 4]]) is True


def test_is_square_false():
    assert is_square([[1, 2, 3], [4, 5, 6]]) is False


def test_irregular_matrix_raises():
    with pytest.raises(MatrixError):
        add([[1, 2], [3, 4, 5]], [[1, 2], [3, 4]])


def test_non_list_input_raises():
    with pytest.raises(MatrixError):
        add(1, 2)


# ---------------------------------------------------------------------------
# add / subtract / scalar_multiply
# ---------------------------------------------------------------------------


def test_add_basic():
    a = [[1, 2], [3, 4]]
    b = [[5, 6], [7, 8]]
    assert add(a, b) == [[6, 8], [10, 12]]


def test_add_with_zero():
    a = [[1, 2], [3, 4]]
    z = [[0, 0], [0, 0]]
    assert add(a, z) == a


def test_add_shape_mismatch_raises():
    with pytest.raises(MatrixError):
        add([[1, 2], [3, 4]], [[1, 2, 3], [4, 5, 6]])


def test_subtract_basic():
    a = [[5, 6], [7, 8]]
    b = [[1, 2], [3, 4]]
    assert subtract(a, b) == [[4, 4], [4, 4]]


def test_scalar_multiply_positive():
    assert scalar_multiply([[1, 2], [3, 4]], 3) == [[3, 6], [9, 12]]


def test_scalar_multiply_negative():
    assert scalar_multiply([[1, -2], [-3, 4]], -1) == [[-1, 2], [3, -4]]


def test_scalar_multiply_zero():
    assert scalar_multiply([[1, 2], [3, 4]], 0) == [[0, 0], [0, 0]]


# ---------------------------------------------------------------------------
# multiply
# ---------------------------------------------------------------------------


def test_multiply_basic():
    a = [[1, 2], [3, 4]]
    b = [[5, 6], [7, 8]]
    assert multiply(a, b) == [[19, 22], [43, 50]]


def test_multiply_with_identity():
    a = [[1, 2, 3], [4, 5, 6]]
    assert multiply(a, identity(3)) == a


def test_multiply_non_square():
    # 2x3 times 3x2
    a = [[1, 2, 3], [4, 5, 6]]
    b = [[1, 2], [3, 4], [5, 6]]
    assert multiply(a, b) == [[22, 28], [49, 64]]


def test_multiply_shape_mismatch_raises():
    with pytest.raises(MatrixError):
        multiply([[1, 2, 3]], [[1, 2], [3, 4]])


# ---------------------------------------------------------------------------
# transpose
# ---------------------------------------------------------------------------


def test_transpose_square():
    assert transpose([[1, 2], [3, 4]]) == [[1, 3], [2, 4]]


def test_transpose_rectangular():
    assert transpose([[1, 2, 3], [4, 5, 6]]) == [[1, 4], [2, 5], [3, 6]]


def test_transpose_tall_to_wide():
    assert transpose([[1, 2, 3, 4]]) == [[1], [2], [3], [4]]


def test_transpose_empty():
    assert transpose([]) == []


# ---------------------------------------------------------------------------
# determinant
# ---------------------------------------------------------------------------


def test_determinant_1x1():
    assert determinant([[42]]) == 42


def test_determinant_2x2():
    # det [[3, 8], [4, 6]] = 3*6 - 8*4 = 18 - 32 = -14
    assert determinant([[3, 8], [4, 6]]) == -14


def test_determinant_3x3():
    # det [[6, 1, 1], [4, -2, 5], [2, 8, 7]] = -306
    a = [[6, 1, 1], [4, -2, 5], [2, 8, 7]]
    assert determinant(a) == -306


def test_determinant_identity():
    assert determinant(identity(5)) == 1


def test_determinant_zero_matrix():
    assert determinant([[0, 0], [0, 0]]) == 0


def test_determinant_non_square_raises():
    with pytest.raises(MatrixError):
        determinant([[1, 2, 3], [4, 5, 6]])


# ---------------------------------------------------------------------------
# inverse
# ---------------------------------------------------------------------------


def test_inverse_2x2():
    # inv [[4, 7], [2, 6]] = (1/10) * [[6, -7], [-2, 4]]
    a = [[4, 7], [2, 6]]
    inv = inverse(a)
    expected = [[0.6, -0.7], [-0.2, 0.4]]
    _approx_equal(inv, expected)


def test_inverse_3x3_roundtrip():
    # det(a) == 1, so a is invertible and a @ inv == I.
    a = [[1, 2, 3], [0, 1, 4], [5, 6, 0]]
    inv = inverse(a)
    product = multiply(a, inv)
    _approx_equal(product, identity(3))


def test_inverse_2x2_roundtrip():
    a = [[3, 2], [7, 5]]
    inv = inverse(a)
    product = multiply(a, inv)
    _approx_equal(product, identity(2))


def test_inverse_singular_raises():
    with pytest.raises(MatrixError):
        inverse([[1, 2], [2, 4]])


def test_inverse_non_square_raises():
    with pytest.raises(MatrixError):
        inverse([[1, 2, 3], [4, 5, 6]])


# ---------------------------------------------------------------------------
# trace / identity
# ---------------------------------------------------------------------------


def test_trace_2x2():
    assert trace([[1, 2], [3, 4]]) == 5


def test_trace_identity():
    assert trace(identity(4)) == 4


def test_trace_non_square_raises():
    with pytest.raises(MatrixError):
        trace([[1, 2, 3], [4, 5, 6]])


def test_identity_shape_and_values():
    i3 = identity(3)
    assert shape(i3) == (3, 3)
    for r in range(3):
        for c in range(3):
            assert i3[r][c] == (1 if r == c else 0)


def test_identity_zero_size():
    assert identity(0) == []