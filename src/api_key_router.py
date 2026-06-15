from typing import Optional, List


class ApiKeyRouter:
    def __init__(self, keys: Optional[List[str]] = None) -> None:
        self._keys = list(keys) if keys is not None else []
        self._index = 0
        self._quota_exceeded = set()

    def register_key(self, key: str) -> None:
        """Register a key with the router so it becomes known/available."""
        if key not in self._keys:
            self._keys.append(key)

    def total_keys(self) -> int:
        """Return the total number of API keys the router was configured with,
        regardless of exhaustion state."""
        return len(self._keys)

    def mark_quota_exhausted(self, key: str) -> None:
        """Flag the given key as quota-exhausted."""
        self._quota_exceeded.add(key)

    def is_quota_exhausted(self, key: str) -> bool:
        """Return True iff the key is currently flagged as quota-exhausted.

        An unknown (never-registered) key is *not* considered exhausted;
        callers should treat that as a separate "unknown key" condition.
        """
        return key in self._quota_exceeded

    def mark_quota_error(self, key: str) -> None:
        self._quota_exceeded.add(key)

    def available_keys(self) -> list:
        return [k for k in self._keys if k not in self._quota_exceeded]

    def is_available(self, key: str) -> bool:
        return key in self._keys and key not in self._quota_exceeded

    def is_quota_error(self, exc: BaseException) -> bool:
        message = str(exc).lower()
        return "quota" in message or "rate limit" in message


if __name__ == "__main__":
    # New spec tests for total_keys
    assert ApiKeyRouter(['a', 'b']).total_keys() == 2
    assert ApiKeyRouter(['x']).total_keys() == 1
    r = ApiKeyRouter(['a', 'b', 'c'])
    r.mark_quota_exhausted('a')
    assert r.total_keys() == 3

    # New spec tests for is_quota_exhausted
    r = ApiKeyRouter(); r.register_key('a')
    assert r.is_quota_exhausted('a') is False

    r = ApiKeyRouter(); r.register_key('a'); r.mark_quota_exhausted('a')
    assert r.is_quota_exhausted('a') is True

    r = ApiKeyRouter()
    assert r.is_quota_exhausted('unknown') is False

    # Existing tests
    r = ApiKeyRouter(["a", "b", "c"])
    assert r._keys == ["a", "b", "c"] and r._index == 0

    r = ApiKeyRouter()
    assert r._keys == [] and r._quota_exceeded == set()

    r = ApiKeyRouter(["x"])
    assert r.is_available("x") is True

    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('quota exceeded')) == True
    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('rate limit hit')) == True
    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('connection refused')) == False
    r = ApiKeyRouter(['a', 'b', 'c']); assert sorted(r.available_keys()) == ['a', 'b', 'c']
    r = ApiKeyRouter(['a', 'b', 'c']); r.mark_quota_error('b'); assert sorted(r.available_keys()) == ['a', 'c']
