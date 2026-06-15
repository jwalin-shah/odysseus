class ApiKeyRouter:
    def __init__(self, keys):
        self._keys = list(keys)
        self._exhausted = set()
        return None

    def mark_quota_error(self, key: str) -> None:
        self._exhausted.add(key)
        return None

    def available_keys(self):
        return [k for k in self._keys if k not in self._exhausted]


r = ApiKeyRouter(['a', 'b']); r.mark_quota_error('a'); assert 'a' not in r.available_keys()
r = ApiKeyRouter(['a', 'b']); r.mark_quota_error('a'); r.mark_quota_error('a'); assert r.available_keys() == ['b']
