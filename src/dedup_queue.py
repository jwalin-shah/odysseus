from typing import Hashable


class DedupQueue:
    def __init__(self):
        self._queue = []
        self._seen = set()

    def push(self, item: object, key: Hashable) -> bool:
        if key in self._seen:
            return False
        self._seen.add(key)
        self._queue.append(item)
        return True

    def __len__(self) -> int:
        return len(self._queue)

    def is_empty(self) -> bool:
        return len(self._queue) == 0
