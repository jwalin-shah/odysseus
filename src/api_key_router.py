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

    def mark_quota_exhausted(self, key: str) -> None:
        """Mark an API key as quota-exhausted.

        Subsequent get_next_key calls will skip this key until reset_all
        is invoked. Marking an already-exhausted key is a no-op.
        """
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

    def all_exhausted(self) -> bool:
        """Return True if every registered key is quota-exhausted."""
        return len(self.available_keys()) == 0 and len(self._keys) > 0

    def reset_all(self) -> None:
        """Clear all quota-exhausted flags and reset the rotation index."""
        self._quota_exceeded.clear()
        self._index = 0

    def get_next_key(self) -> Optional[str]:
        """Return the next available (non-exhausted) key, or None.

        Walks the registered key list starting at the current index,
        skipping any key currently flagged as quota-exhausted. After a
        full pass with no available key, returns None.
        """
        if not self._keys:
            return None
        n = len(self._keys)
        for _ in range(n):
            key = self._keys[self._index]
            self._index = (self._index + 1) % n
            if key not in self._quota_exceeded:
                return key
        return None


if __name__ == "__main__":
    # New spec tests for mark_quota_exhausted
    r = ApiKeyRouter(['a', 'b', 'c']); r.mark_quota_exhausted('b')
    assert r.available_keys() == ['a', 'c']

    r = ApiKeyRouter(['a']); r.mark_quota_exhausted('a')
    assert r.all_exhausted() is True

    r = ApiKeyRouter(['a', 'b'])
    r.mark_quota_exhausted('a')
    r.mark_quota_exhausted('a')
    assert r.available_keys() == ['b']

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
    assert r.is_quota_error(Exception('quota exceeded')) is True
    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('rate limit hit')) is True
    r = ApiKeyRouter([])
    assert r.is_quota_error(Exception('connection refused')) is False

    r = ApiKeyRouter(['a', 'b', 'c'])
    assert sorted(r.available_keys()) == ['a', 'b', 'c']
    r = ApiKeyRouter(['a', 'b', 'c']); r.mark_quota_error('b')
    assert sorted(r.available_keys()) == ['a', 'c']

    # reset_all and get_next_key sanity checks
    r = ApiKeyRouter(['a', 'b', 'c'])
    r.mark_quota_exhausted('a')
    assert r.get_next_key() == 'b'
    r.mark_quota_exhausted('b')
    assert r.get_next_key() == 'c'
    r.mark_quota_exhausted('c')
    assert r.get_next_key() is None
    r.reset_all()
    assert sorted(r.available_keys()) == ['a', 'b', 'c']
    assert r.all_exhausted() is False
