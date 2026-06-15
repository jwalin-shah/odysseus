from typing import Optional, List


class ApiKeyRouter:
    def __init__(self, keys: Optional[List[str]] = None) -> None:
        self._keys = list(keys) if keys is not None else []
        self._index = 0
        self._quota_exceeded = set()

    def register_key(self, key: str) -> None:
        if key not in self._keys:
            self._keys.append(key)

    def mark_quota_error(self, key: str) -> None:
        self._quota_exceeded.add(key)

    def mark_quota_exhausted(self, key: str) -> None:
        self._quota_exceeded.add(key)

    def reset_quota(self, key: str) -> bool:
        if key in self._quota_exceeded:
            self._quota_exceeded.discard(key)
            return True
        return False

    def is_quota_exhausted(self, key: str) -> bool:
        return key in self._quota_exceeded

    def available_keys(self) -> list:
        return [k for k in self._keys if k not in self._quota_exceeded]

    def is_available(self, key: str) -> bool:
        return key in self._keys and key not in self._quota_exceeded

    def is_quota_error(self, exc: BaseException) -> bool:
        message = str(exc).lower()
        return "quota" in message or "rate limit" in message


if __name__ == "__main__":
    # Spec tests for reset_quota
    r = ApiKeyRouter(); r.register_key('a'); r.mark_quota_exhausted('a'); assert r.reset_quota('a') is True
    r = ApiKeyRouter(); r.register_key('a'); assert r.reset_quota('a') is False
    r = ApiKeyRouter(); r.register_key('a'); r.reset_quota('a'); assert r.is_quota_exhausted('a') is False

    # Spec tests
    r = ApiKeyRouter(["a", "b", "c"])
    assert r._keys == ["a", "b", "c"] and r._index == 0

    r = ApiKeyRouter()
    assert r._keys == [] and r._quota_exceeded == set()

    r = ApiKeyRouter(["x"])
    assert r.is_available("x") is True

    # Existing tests
    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('quota exceeded')) == True
    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('rate limit hit')) == True
    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('connection refused')) == False
    r = ApiKeyRouter(['a', 'b', 'c']); assert sorted(r.available_keys()) == ['a', 'b', 'c']
    r = ApiKeyRouter(['a', 'b', 'c']); r.mark_quota_error('b'); assert sorted(r.available_keys()) == ['a', 'c']
