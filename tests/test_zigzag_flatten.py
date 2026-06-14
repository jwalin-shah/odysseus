"""Tests for ``zigzag_flatten``."""

import pytest

from zigzag_flatten import TreeNode, zigzag_flatten


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _build_complete(values):
    """Build a complete binary tree from a level-order list of values.

    ``None`` entries in ``values`` are preserved as gaps so the shape of
    the tree stays predictable across the tests.
    """
    if not values:
        return None
    nodes = [None if v is None else TreeNode(v) for v in values]
    kids = nodes[1:]
    for parent in nodes:
        if parent is None:
            continue
        if kids:
            parent.left = kids.pop(0)
        if kids:
            parent.right = kids.pop(0)
    return nodes[0]


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------
def test_empty_tree_returns_empty_list():
    """``None`` root should produce an empty list (not raise)."""
    assert zigzag_flatten(None) == []


def test_single_node():
    """A tree with a single node returns a one-element list."""
    root = TreeNode(42)
    assert zigzag_flatten(root) == [42]


def test_two_level_tree():
    """
        1
       / \\
      2   3
    Level 0 (L->R): 1
    Level 1 (R->L): 2, 3  ->  [3, 2]
    """
    root = TreeNode(1, TreeNode(2), TreeNode(3))
    assert zigzag_flatten(root) == [1, 3, 2]


def test_three_level_complete_tree():
    """
          1
        /   \\
       2     3
      / \\   / \\
     4   5 6   7
    Level 0 (L->R): 1
    Level 1 (R->L): 2, 3          ->  [3, 2]
    Level 2 (L->R): 4, 5, 6, 7
    """
    root = _build_complete([1, 2, 3, 4, 5, 6, 7])
    assert zigzag_flatten(root) == [1, 3, 2, 4, 5, 6, 7]


def test_four_level_complete_tree():
    """
    Full 4-level tree with values 1..15.

    Level 0 (L->R): 1
    Level 1 (R->L): 2, 3          ->  [3, 2]
    Level 2 (L->R): 4, 5, 6, 7
    Level 3 (R->L): 8..15         ->  [15, 14, 13, 12, 11, 10, 9, 8]
    """
    root = _build_complete(list(range(1, 16)))
    assert zigzag_flatten(root) == [
        1, 3, 2, 4, 5, 6, 7, 15, 14, 13, 12, 11, 10, 9, 8,
    ]


def test_left_skewed_tree():
    """
      1
     /
    2
   /
  3

    Level 0: 1
    Level 1 (R->L): 2
    Level 2 (L->R): 3
    """
    root = TreeNode(1)
    root.left = TreeNode(2)
    root.left.left = TreeNode(3)
    assert zigzag_flatten(root) == [1, 2, 3]


def test_right_skewed_tree():
    """
    1
     \\
      2
       \\
        3

    Level 0: 1
    Level 1 (R->L): 2
    Level 2 (L->R): 3
    """
    root = TreeNode(1)
    root.right = TreeNode(2)
    root.right.right = TreeNode(3)
    assert zigzag_flatten(root) == [1, 2, 3]


def test_works_with_string_values():
    """The implementation should not assume a numeric value type."""
    #          'a'
    #         /   \\
    #       'b'   'c'
    #       /
    #     'd'
    root = TreeNode("a", TreeNode("b", TreeNode("d")), TreeNode("c"))
    # Level 0: a
    # Level 1 (R->L): b, c -> [c, b]
    # Level 2 (L->R): d
    assert zigzag_flatten(root) == ["a", "c", "b", "d"]


def test_does_not_mutate_tree():
    """Calling ``zigzag_flatten`` must not change the shape of the tree."""
    root = _build_complete([1, 2, 3, 4, 5, 6, 7])
    snapshot_left = root.left.val
    snapshot_right = root.right.val
    zigzag_flatten(root)
    assert root.left.val == snapshot_left
    assert root.right.val == snapshot_right
    # Spot-check that the tree is still traversable in a normal way
    assert root.left.left.val == 4
    assert root.right.right.val == 7


def test_returns_independent_list():
    """Successive calls should return distinct (not shared) list objects."""
    root = TreeNode(1, TreeNode(2), TreeNode(3))
    first = zigzag_flatten(root)
    second = zigzag_flatten(root)
    assert first == second == [1, 3, 2]
    assert first is not second


@pytest.mark.parametrize(
    "values, expected",
    [
        ([], []),
        ([1], [1]),
        ([1, 2, 3], [1, 3, 2]),
        ([1, 2, 3, 4, 5, 6, 7], [1, 3, 2, 4, 5, 6, 7]),
        ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15],
         [1, 3, 2, 4, 5, 6, 7, 15, 14, 13, 12, 11, 10, 9, 8]),
    ],
)
def test_parametrized_shapes(values, expected):
    """A handful of shapes verified together for clarity."""
    root = _build_complete(values)
    assert zigzag_flatten(root) == expected