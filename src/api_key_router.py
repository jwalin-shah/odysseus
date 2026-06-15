class ApiKeyRouter:
    def __init__(self, keys):
        self._keys = list(keys)
        self._exhausted = set()

    def mark_quota_error(self, key: str) -> None:
        self._exhausted.add(key)

    def available_keys(self):
        return [k for k in self._keys if k not in self._exhausted]
