from typing import Iterator


class DedupQueue:
    def __init__(self):
        self._items = []
        self._seen_keys = set()

    def push(self, item, key) -> bool:
        if key in self._seen_keys:
            return False
        self._seen_keys.add(key)
        self._items.append(item)
        return True

    def __iter__(self) -> Iterator[object]:
        return iter(self._items)
