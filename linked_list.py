from __future__ import annotations

from typing import Any

try:
    from .node import Node
except ImportError:  # pragma: no cover - fallback when not used as a package
    from node import Node


def append(self, val: Any) -> None:
    """Append a node with the given value to the end. O(1)."""
    node = Node(val)
    if self.tail is None:
        self.head = self.tail = node
    else:
        self.tail.next = node
        self.tail = node
    self._size += 1
