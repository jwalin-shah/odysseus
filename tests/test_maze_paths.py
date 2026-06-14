import pytest

from maze_paths import maze_paths


def test_single_cell_open():
    """A single open cell is both the start and the end."""
    assert maze_paths([[1]]) == [[(0, 0)]]


def test_single_cell_blocked():
    """A single blocked cell produces no path."""
    assert maze_paths([[0]]) == []


def test_2x2_all_open():
    """A 2x2 maze with all open cells has exactly two paths."""
    maze = [[1, 1], [1, 1]]
    paths = maze_paths(maze)
    assert len(paths) == 2
    expected = {
        ((0, 0), (0, 1), (1, 1)),
        ((0, 0), (1, 0), (1, 1)),
    }
    assert {tuple(p) for p in paths} == expected


def test_3x3_six_unique_paths():
    """A 3x3 open grid has C(4,2) = 6 unique paths."""
    maze = [[1, 1, 1], [1, 1, 1], [1, 1, 1]]
    paths = maze_paths(maze)
    assert len(paths) == 6
    for p in paths:
        assert p[0] == (0, 0)
        assert p[-1] == (2, 2)
        # Two rights and two downs plus the starting cell -> 5 cells.
        assert len(p) == 5
        # Every step must be a valid right or down move and stay open.
        for (r, c) in p:
            assert maze[r][c] == 1


def test_with_obstacles():
    """Maze with obstacles still yields the correct set of paths."""
    maze = [
        [1, 0, 0],
        [1, 1, 0],
        [1, 1, 1],
    ]
    paths = maze_paths(maze)
    assert len(paths) == 2
    expected = {
        ((0, 0), (1, 0), (2, 0), (2, 1), (2, 2)),
        ((0, 0), (1, 0), (1, 1), (2, 1), (2, 2)),
    }
    assert {tuple(p) for p in paths} == expected


def test_start_blocked():
    """If the start cell is blocked, no path exists."""
    assert maze_paths([[0, 1], [1, 1]]) == []


def test_end_blocked():
    """If the end cell is blocked, no path exists."""
    assert maze_paths([[1, 1], [1, 0]]) == []


def test_no_path_through_obstacles():
    """A maze whose interior is fully blocked yields no path."""
    maze = [
        [1, 0, 0],
        [0, 0, 0],
        [0, 0, 1],
    ]
    assert maze_paths(maze) == []


def test_empty_maze_inputs():
    """Empty inputs should be handled gracefully."""
    assert maze_paths([]) == []
    assert maze_paths([[]]) == []


def test_paths_stay_on_open_cells():
    """Every returned path must consist exclusively of open cells."""
    maze = [
        [1, 1, 1, 1],
        [0, 0, 0, 1],
        [1, 1, 1, 1],
        [1, 0, 0, 1],
    ]
    paths = maze_paths(maze)
    assert len(paths) >= 1
    for p in paths:
        assert p[0] == (0, 0)
        assert p[-1] == (3, 3)
        for (r, c) in p:
            assert maze[r][c] == 1
            # Verify that every consecutive step is a legal right/down move.
        for (r1, c1), (r2, c2) in zip(p, p[1:]):
            assert (r2 == r1 and c2 == c1 + 1) or (c2 == c1 and r2 == r1 + 1)