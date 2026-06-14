from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class Node:
    """A node in a singly linked list."""
    val: Any
    next: Optional["Node"] = field(default=None, repr=False, compare=False)


class LinkedList:
    """Singly linked list with O(1) head ops and O(n) tail/index ops."""

    def __init__(self) -> None:
        self.head: Optional[Node] = None
        self.tail: Optional[Node] = None
        self._size: int = 0

    def __len__(self) -> int:
        return self._size

    def __iter__(self):
        cur = self.head
        while cur is not None:
            yield cur.val
            cur = cur.next

    def __repr__(self) -> str:
        return "LinkedList([" + ", ".join(repr(v) for v in self) + "])"

    # ---------- core mutators ----------

    def append(self, val: Any) -> None:
        """Append a node with the given value to the end. O(1)."""
        node = Node(val)
        if self.tail is None:
            self.head = self.tail = node
        else:
            self.tail.next = node
            self.tail = node
        self._size += 1

    def prepend(self, val: Any) -> None:
        """Prepend a node with the given value to the start. O(1)."""
        node = Node(val, next=self.head)
        self.head = node
        if self.tail is None:
            self.tail = node
        self._size += 1

    def insert(self, idx: int, val: Any) -> None:
        """Insert val at index idx. Supports negative indices. O(n)."""
        if idx < 0:
            idx = max(0, self._size + idx)
        if idx <= 0:
            self.prepend(val)
            return
        if idx >= self._size:
            self.append(val)
            return
        prev = self._node_at(idx - 1)
        assert prev is not None
        prev.next = Node(val, next=prev.next)
        self._size += 1

    def delete(self, val: Any) -> bool:
        """Delete the first node with value val. Returns True if removed. O(n)."""
        prev: Optional[Node] = None
        cur = self.head
        while cur is not None:
            if cur.val == val:
                if prev is None:
                    self.head = cur.next
                else:
                    prev.next = cur.next
                if cur is self.tail:
                    self.tail = prev
                self._size -= 1
                if self._size == 0:
                    self.head = self.tail = None
                return True
            prev = cur
            cur = cur.next
        return False

    # ---------- structural ops ----------

    def reverse(self) -> None:
        """Reverse the list in place. O(n)."""
        prev: Optional[Node] = None
        cur = self.head
        self.tail = self.head
        while cur is not None:
            nxt = cur.next
            cur.next = prev
            prev = cur
            cur = nxt
        self.head = prev

    def find_middle(self) -> Optional[Node]:
        """Return the middle node (lower middle for even length). O(n)."""
        slow = self.head
        fast = self.head
        while fast is not None and fast.next is not None:
            slow = slow.next if slow is not None else None
            fast = fast.next.next
        return slow

    def has_cycle(self) -> bool:
        """Return True if the list has a cycle. O(n) time, O(1) space."""
        slow = self.head
        fast = self.head
        while fast is not None and fast.next is not None:
            slow = slow.next if slow is not None else None
            fast = fast.next.next
            if slow is fast:
                return True
        return False

    def remove_nth_from_end(self, n: int) -> None:
        """Remove the nth node from the end (1-indexed). O(n)."""
        if n <= 0 or self._size == 0:
            raise IndexError("n must be a positive integer within range")
        target_from_head = self._size - n
        if target_from_head <= 0:
            old_head = self.head
            self.head = old_head.next if old_head is not None else None
            if self._size == 1:
                self.tail = None
            self._size -= 1
            return
        prev = self._node_at(target_from_head - 1)
        assert prev is not None and prev.next is not None
        removed = prev.next
        prev.next = removed.next
        if removed is self.tail:
            self.tail = prev
        self._size -= 1
        if self._size == 0:
            self.head = self.tail = None

    # ---------- helpers ----------

    def _node_at(self, idx: int) -> Optional[Node]:
        """Return node at non-negative index idx, or None if out of range. O(n)."""
        if idx < 0 or idx >= self._size:
            return None
        cur = self.head
        for _ in range(idx):
            assert cur is not None
            cur = cur.next
        return cur