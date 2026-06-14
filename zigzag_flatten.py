"""Zigzag (spiral) level-order traversal of a binary tree, flattened to a list."""

from typing import Optional, List, Any


class TreeNode:
    """Simple binary tree node with a value and left/right children."""

    __slots__ = ("val", "left", "right")

    def __init__(
        self,
        val: Any = 0,
        left: Optional["TreeNode"] = None,
        right: Optional["TreeNode"] = None,
    ) -> None:
        self.val = val
        self.left = left
        self.right = right

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"TreeNode({self.val!r})"


def zigzag_flatten(root) -> List[Any]:
    """
    Perform a zigzag (spiral) level-order traversal of a binary tree
    and return the values as a single flat list.

    The traversal alternates direction at every level:

        * Level 0  -> left  to right
        * Level 1  -> right to left
        * Level 2  -> left  to right
        * ...

    Parameters
    ----------
    root : TreeNode | None
        The root of the binary tree. Every node must expose ``val``,
        ``left`` and ``right`` attributes.  ``None`` represents an
        empty tree.

    Returns
    -------
    list
        A flat list of node values in zigzag order.  Returns an empty
        list for an empty tree.

    Examples
    --------
    >>> root = TreeNode(1, TreeNode(2), TreeNode(3))
    >>> zigzag_flatten(root)
    [1, 3, 2]
    """
    if root is None:
        return []

    result: List[Any] = []
    current_level = [root]
    left_to_right = True

    while current_level:
        next_level = []
        level_values: List[Any] = []

        for node in current_level:
            level_values.append(node.val)
            left = getattr(node, "left", None)
            right = getattr(node, "right", None)
            if left is not None:
                next_level.append(left)
            if right is not None:
                next_level.append(right)

        if not left_to_right:
            level_values.reverse()

        result.extend(level_values)
        current_level = next_level
        left_to_right = not left_to_right

    return result


__all__ = ["TreeNode", "zigzag_flatten"]