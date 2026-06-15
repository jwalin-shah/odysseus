from collections import deque
from typing import Any, Deque, Hashable, Set


class DedupQueue:
    """A FIFO queue that deduplicates incoming items by a hashable key.

    Each item is pushed with a value and a key. If the same key is pushed
    again before the original item is consumed, the duplicate is silently
    dropped, ensuring each key is represented at most once in the queue.
    """

    def __init__(self) -> None:
        self._items: Deque[tuple] = deque()
        self._keys: Set[Hashable] = set()

    def push(self, value: Any, key: Hashable) -> bool:
        """Push ``value`` associated with ``key``.

        Returns ``True`` if the item was accepted, or ``False`` if a
        value with the same key is already in the queue.
        """
        if key in self._keys:
            return False
        self._items.append((value, key))
        self._keys.add(key)
        return True

    def pop(self) -> Any:
        """Remove and return the value at the front of the queue.

        The corresponding key is also removed from the dedup set so that
        the same key may be pushed again later.

        Raises ``IndexError`` if the queue is empty.
        """
        if not self._items:
            raise IndexError("pop from empty DedupQueue")
        value, key = self._items.popleft()
        self._keys.discard(key)
        return value

    def peek(self) -> Any:
        """Return the value at the front of the queue without removing it.

        Raises ``IndexError`` if the queue is empty.
        """
        if not self._items:
            raise IndexError("peek from empty DedupQueue")
        return self._items[0][0]

    def is_empty(self) -> bool:
        """Return ``True`` if the queue has no items."""
        return len(self._items) == 0

    def __len__(self) -> int:
        return len(self._items)

    def contains_key(self, key: Hashable) -> bool:
        """Return True if a key has already been accepted into the queue,
        False otherwise.
        """
        return key in self._keys
