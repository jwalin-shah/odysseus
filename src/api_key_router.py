class ApiKeyRouter:
    def __init__(self, keys):
        self._keys = list(keys)
        self._exhausted = set()

    def mark_quota_error(self, key: str) -> None:
        self._exhausted.add(key)

    def available_keys(self) -> list:
        return [k for k in self._keys if k not in self._exhausted]

    def is_quota_error(self, exc: BaseException) -> bool:
        message = str(exc).lower()
        return "quota" in message or "rate limit" in message


if __name__ == "__main__":
    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('quota exceeded')) == True
    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('rate limit hit')) == True
    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('connection refused')) == False
    r = ApiKeyRouter(['a', 'b', 'c']); assert sorted(r.available_keys()) == ['a', 'b', 'c']
    r = ApiKeyRouter(['a', 'b', 'c']); r.mark_quota_error('b'); assert sorted(r.available_keys()) == ['a', 'c']
