class ApiKeyRouter:
    def __init__(self, keys):
        self._keys = list(keys)
        self._exhausted = set()
        self._index = 0

    def available_keys(self):
        return [k for k in self._keys if k not in self._exhausted]

    def mark_quota_exceeded(self, key: str) -> str | None:
        self._exhausted.add(key)
        self._index += 1
        while self._index < len(self._keys):
            if self._keys[self._index] not in self._exhausted:
                return self._keys[self._index]
            self._index += 1
        return None
