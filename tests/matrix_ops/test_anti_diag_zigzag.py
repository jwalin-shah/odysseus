import importlib.util
import os

# Load the implementation module directly from its file path to avoid
# relying on the `matrix_ops` directory being a proper Python package
# (e.g., having an __init__.py).
_impl_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "matrix_ops", "anti_diag_zigzag.py",
)
_impl_path = os.path.normpath(_impl_path)

_spec = importlib.util.spec_from_file_location(
    "_anti_diag_zigzag_impl", _impl_path
)
_impl_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_impl_module)
anti_diag_zigzag = _impl_module.anti_diag_zigzag


def test_basic_3x3_zigzag():
    """Canonical 3x3 matrix in anti-diagonal zigzag order."""
    matrix = [
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
    ]
    # s=0 (even): [1]
    # s=1 (odd):  [2,4] -> [4,2]
    # s=2 (even): [3,5,7]
    # s=3 (odd):  [6,8] -> [8,6]
    # s=4 (even): [9]
    expected = [1, 4, 2, 3, 5, 7, 8, 6, 9]
    assert anti_diag_zigzag(matrix) == expected


def test_empty_matrix():
    """An empty matrix yields an empty list."""
    assert anti_diag_zigzag([]) == []


def test_matrix_with_empty_first_row():
    """A matrix whose first row is empty yields an empty list."""
    assert anti_diag_zigzag([[]]) == []


def test_single_element_matrix():
    """A 1x1 matrix returns its single element."""
    assert anti_diag_zigzag([[42]]) == [42]


def test_single_row_matrix():
    """A 1xN matrix returns its elements in order."""
    # Only one element per anti-diagonal, so direction reversal
    # does not change the result.
    assert anti_diag_zigzag([[1, 2, 3, 4]]) == [1, 2, 3, 4]


def test_single_column_matrix():
    """An Mx1 matrix returns its elements in order."""
    assert anti_diag_zigzag([[1], [2], [3], [4]]) == [1, 2, 3, 4]


def test_2x3_rectangular():
    """2x3 rectangular matrix."""
    matrix = [
        [1, 2, 3],
        [4, 5, 6],
    ]
    # s=0: [1]
    # s=1: [2,4] -> [4,2]
    # s=2: [3,5]
    # s=3: [6]
    expected = [1, 4, 2, 3, 5, 6]
    assert anti_diag_zigzag(matrix) == expected


def test_3x2_rectangular():
    """3x2 rectangular matrix."""
    matrix = [
        [1, 2],
        [3, 4],
        [5, 6],
    ]
    # s=0: [1]
    # s=1: [2,3] -> [3,2]
    # s=2: [4,5]
    # s=3: [6]
    expected = [1, 3, 2, 4, 5, 6]
    assert anti_diag_zigzag(matrix) == expected


def test_preserves_all_elements_4x4():
    """Result must contain exactly the same multiset of elements as input."""
    matrix = [
        [10, 20, 30, 40],
        [50, 60, 70, 80],
        [90, 100, 110, 120],
        [130, 140, 150, 160],
    ]
    result = anti_diag_zigzag(matrix)
    assert len(result) == len(matrix) * len(matrix[0])
    assert sorted(result) == sorted(
        elem for row in matrix for elem in row
    )