def append(self, val: Any) -> None:
    """Append a node with the given value to the end. O(1)."""
    node = Node(val)
    if self.tail is None:
        self.head = self.tail = node
    else:
        self.tail.next = node
        self.tail = node
    self._size += 1
