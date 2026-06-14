from missions.concentric_ring_mn_maxima_collector import (
    concentric_ring_mn_maxima_collector,
)


def test_empty_matrix():
    assert concentric_ring_mn_maxima_collector([]) == []


def test_single_cell():
    assert concentric_ring_mn_maxima_collector([[7]]) == [7]


def test_single_zero():
    assert concentric_ring_mn_maxima_collector([[0]]) == [0]


def test_max_on_inner_ring_not_outer():
    # 3x3: center is 100, outer ring is all 1s.
    matrix = [
        [1, 1, 1],
        [1, 100, 1],
        [1, 1, 1],
    ]
    assert concentric_ring_mn_maxima_collector(matrix) == [1, 100]


def test_max_on_outer_ring_not_inner():
    # 3x3: corners are 100, center is 1, edges are 0.
    matrix = [
        [100, 0, 100],
        [0, 1, 0],
        [100, 0, 100],
    ]
    assert concentric_ring_mn_maxima_collector(matrix) == [100, 1]


def test_zero_with_single_nonzero():
    # 3x3: outer ring is 0, center is 5.
    matrix = [
        [0, 0, 0],
        [0, 5, 0],
        [0, 0, 0],
    ]
    assert concentric_ring_mn_maxima_collector(matrix) == [0, 5]


def test_2x2_matrix_single_ring():
    # 2x2 has only one ring containing all four cells.
    matrix = [
        [1, 2],
        [3, 4],
    ]
    assert concentric_ring_mn_maxima_collector(matrix) == [4]


def test_4x4_matrix_two_rings():
    matrix = [
        [1, 2, 3, 4],
        [5, 6, 7, 8],
        [9, 10, 11, 12],
        [13, 14, 15, 16],
    ]
    # ring 0 (outer 12 cells): max = 16
    # ring 1 (inner 4 cells): max = 11
    assert concentric_ring_mn_maxima_collector(matrix) == [16, 11]


def test_5x5_matrix_three_rings():
    matrix = [
        [1, 1, 1, 1, 1],
        [1, 2, 2, 2, 1],
        [1, 2, 3, 2, 1],
        [1, 2, 2, 2, 1],
        [1, 1, 1, 1, 1],
    ]
    # ring 0 (border of 1s): max = 1
    # ring 1 (all 2s): max = 2
    # ring 2 (center): max = 3
    assert concentric_ring_mn_maxima_collector(matrix) == [1, 2, 3]


def test_all_equal_3x3():
    matrix = [
        [5, 5, 5],
        [5, 5, 5],
        [5, 5, 5],
    ]
    assert concentric_ring_mn_maxima_collector(matrix) == [5, 5]


def test_negative_values_3x3():
    matrix = [
        [-1, -2, -3],
        [-4, -5, -6],
        [-7, -8, -9],
    ]
    # ring 0: max = -1, ring 1: max = -5
    assert concentric_ring_mn_maxima_collector(matrix) == [-1, -5]


def test_non_square_3x5():
    matrix = [
        [1, 2, 3, 4, 5],
        [6, 7, 8, 9, 10],
        [11, 12, 13, 14, 15],
    ]
    # ring 0: max = 15
    # ring 1 (inner row): max = 9
    assert concentric_ring_mn_maxima_collector(matrix) == [15, 9]


def test_non_square_5x3():
    matrix = [
        [1, 6, 11],
        [2, 7, 12],
        [3, 8, 13],
        [4, 9, 14],
        [5, 10, 15],
    ]
    # ring 0: max = 15
    # ring 1 (inner column): max = 9
    assert concentric_ring_mn_maxima_collector(matrix) == [15, 9]


def test_row_vector():
    matrix = [[3, 1, 4, 1, 5, 9, 2, 6]]
    assert concentric_ring_mn_maxima_collector(matrix) == [9]


def test_column_vector():
    matrix = [[3], [1], [4], [1], [5]]
    assert concentric_ring_mn_maxima_collector(matrix) == [5]


def test_returns_list_type():
    result = concentric_ring_mn_maxima_collector([[1, 2], [3, 4]])
    assert isinstance(result, list)


def test_6x6_matrix_three_rings():
    matrix = [
        [1, 1, 1, 1, 1, 1],
        [1, 2, 2, 2, 2, 1],
        [1, 2, 3, 3, 2, 1],
        [1, 2, 3, 3, 2, 1],
        [1, 2, 2, 2, 2, 1],
        [1, 1, 1, 1, 1, 1],
    ]
    # ring 0: max = 1
    # ring 1: max = 2
    # ring 2: max = 3
    assert concentric_ring_mn_maxima_collector(matrix) == [1, 2, 3]


def test_large_max_in_outer_corner():
    matrix = [
        [50, 1, 1, 1],
        [1, 1, 1, 1],
        [1, 1, 1, 1],
        [1, 1, 1, 1],
    ]
    # ring 0: max = 50, ring 1: max = 1
    assert concentric_ring_mn_maxima_collector(matrix) == [50, 1]


def test_floats_supported():
    matrix = [
        [0.5, 0.5, 0.5],
        [0.5, 2.25, 0.5],
        [0.5, 0.5, 0.5],
    ]
    assert concentric_ring_mn_maxima_collector(matrix) == [0.5, 2.25]