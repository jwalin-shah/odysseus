class DedupQueue:
    """A queue that deduplicates items by key.

    Pushing a value with a key that already exists is a no-op;
    the original value for that key is retained and ordering is
    preserved.
    """

    def __init__(self) -> None:
        self._items = []
        self._keys = set()

    def push(self, value, key) -> None:
        if key in self._keys:
            return
        self._keys.add(key)
        self._items.append((key, value))

    def pop(self):
        if not self._items:
            raise IndexError("pop from empty DedupQueue")
        key, value = self._items.pop(0)
        self._keys.discard(key)
        return value

    def __len__(self) -> int:
        return len(self._items)

    def __contains__(self, key) -> bool:
        return key in self._keys

    def __repr__(self) -> str:
        return f"DedupQueue({self._items!r})"
