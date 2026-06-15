class ApiKeyRouter:
    def __init__(self, keys):
        self._all_keys = list(keys)
        self._exhausted = set()

    def mark_quota_exceeded(self, key):
        if key in self._all_keys:
            self._exhausted.add(key)

    def available_keys(self):
        return [k for k in self._all_keys if k not in self._exhausted]

    def next_key(self):
        available = self.available_keys()
        if not available:
            return None
        return available[0]

    def reset_key(self, key):
        if key not in self._all_keys:
            return
        self._exhausted.discard(key)
