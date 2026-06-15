class DedupQueue:
    """A FIFO queue that deduplicates items by a hashable key."""

    def __init__(self) -> None:
        """Initialize an empty DedupQueue with an internal FIFO list and a set of seen keys."""
        self._items: list = []
        self._seen: set = set()

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def __contains__(self, key) -> bool:
        return key in self._seen

    def push(self, key, value=None) -> bool:
        """Enqueue value under key. Returns True if added, False if key already seen."""
        if key in self._seen:
            return False
        self._seen.add(key)
        self._items.append(value if value is not None else key)
        return True
