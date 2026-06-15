class DedupQueue:
    def __init__(self):
        self._items = []
        self._keys = set()

    def push(self, item, key) -> None:
        if key in self._keys:
            return
        self._keys.add(key)
        self._items.append(item)

    def to_list(self) -> list:
        return list(self._items)
