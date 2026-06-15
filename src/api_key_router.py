class ApiKeyRouter:
    def __init__(self, keys: list) -> None:
        self._keys = list(keys)
        self._exhausted = set()

    def mark_quota_error(self, key: str) -> None:
        self._exhausted.add(key)

    def reset(self, key=None) -> None:
        if key is None:
            self._exhausted.clear()
        else:
            self._exhausted.discard(key)

    def available_keys(self):
        return [k for k in self._keys if k not in self._exhausted]


r = ApiKeyRouter(['k1', 'k2', 'k3']); assert sorted(r.available_keys()) == ['k1', 'k2', 'k3']
assert ApiKeyRouter([]).available_keys() == []
r = ApiKeyRouter(['a', 'b']); r.mark_quota_error('a'); r.reset('a'); assert 'a' in r.available_keys()
r = ApiKeyRouter(['a', 'b']); r.mark_quota_error('a'); r.mark_quota_error('b'); r.reset(); assert sorted(r.available_keys()) == ['a', 'b']
