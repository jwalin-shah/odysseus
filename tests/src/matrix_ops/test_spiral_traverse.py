import os
import importlib.util


def _load_module():
    """Load the spiral_traverse module directly from its file path.

    This bypasses the need for __init__.py files in the src/matrix_ops/
    package directory, allowing the test to import the implementation
    regardless of the package configuration.
    """
    # This test file lives at: tests/src/matrix_ops/test_spiral_traverse.py
    # We need to reach:  <project_root>/src/matrix_ops/spiral_traverse.py
    test_dir = os.path.dirname(os.path.abspath(__file__))
    # tests/src/matrix_ops/ -> tests/src/ -> tests/ -> project_root
    project_root = os.path.abspath(os.path.join(test_dir, "..", "..", ".."))
    module_path = os.path.join(project_root, "src", "matrix_ops", "spiral_traverse.py")

    spec = importlib.util.spec_from_file_location("spiral_traverse", module_path)
    assert spec is not None and spec.loader is not None, (
        f"Could not load module from {module_path}"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_mod = _load_module()
spiral_traverse = _mod.spiral_traverse


def test_spiral_traverse_3x3():
    matrix = [
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
    ]
    assert spiral_traverse(matrix) == [1, 2, 3, 6, 9, 8, 7, 4, 5]


def test_spiral_traverse_empty_matrix():
    assert spiral_traverse([]) == []
    assert spiral_traverse([[]]) == []


def test_spiral_traverse_single_element():
    assert spiral_traverse([[42]]) == [42]


def test_spiral_traverse_single_row():
    assert spiral_traverse([[1, 2, 3, 4, 5]]) == [1, 2, 3, 4, 5]


def test_spiral_traverse_single_column():
    assert spiral_traverse([[1], [2], [3], [4]]) == [1, 2, 3, 4]


def test_spiral_traverse_2x2():
    matrix = [
        [1, 2],
        [3, 4],
    ]
    assert spiral_traverse(matrix) == [1, 2, 4, 3]


def test_spiral_traverse_4x4():
    matrix = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12],
        [13, 14, 15, 16],
    ]
    assert spiral_traverse(matrix) == [
        1, 2, 3, 4, 8, 12, 16, 15, 14, 13, 9, 5, 6, 7, 11, 10
    ]


def test_spiral_traverse_rectangular_more_cols_than_rows():
    matrix = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12],
    ]
    assert spiral_traverse(matrix) == [
        1, 2, 3, 4, 8, 12, 11, 10, 9, 5, 6, 7
    ]


def test_spiral_traverse_rectangular_more_rows_than_cols():
    matrix = [
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
        [10, 11, 12],
    ]
    assert spiral_traverse(matrix) == [
        1, 2, 3, 6, 9, 12, 11, 10, 7, 4, 5, 8
    ]


def test_spiral_traverse_with_negative_numbers():
    matrix = [
        [-1, -2, -3],
        [-4, -5, -6],
    ]
    assert spiral_traverse(matrix) == [-1, -2, -3, -6, -5, -4]