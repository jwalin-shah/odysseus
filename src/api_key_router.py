from typing import List, Optional


class ApiKeyRouter:
    """Round-robin API key router with quota-exhaustion tracking."""

    def __init__(self, keys: list[str]) -> None:
        """Initialize the router with an ordered list of API keys.

        Sets up an empty exhausted set and places the round-robin
        cursor at position 0.
        """
        self._keys: List[str] = list(keys)
        self._exhausted: set[str] = set()
        self._cursor: int = 0

    def total_keys(self) -> int:
        """Return the total number of registered API keys."""
        return len(self._keys)

    def keys(self) -> List[str]:
        """Return a copy of the ordered list of registered keys."""
        return list(self._keys)

    def is_exhausted(self, key: str) -> bool:
        """Return True iff the key has been flagged as exhausted."""
        return key in self._exhausted

    def mark_exhausted(self, key: str) -> None:
        """Flag the given key as exhausted."""
        self._exhausted.add(key)

    def reset_exhausted(self, key: str) -> None:
        """Clear the exhausted flag for the given key, if present."""
        self._exhausted.discard(key)

    def exhausted_keys(self) -> List[str]:
        """Return a list of keys currently flagged as exhausted."""
        return [k for k in self._keys if k in self._exhausted]

    def available_keys(self) -> List[str]:
        """Return the registered keys that are not currently exhausted."""
        return [k for k in self._keys if k not in self._exhausted]

    def next_key(self) -> Optional[str]:
        """Return the next available key in round-robin order.

        Skips any key present in the exhausted set. Returns None when
        no keys are registered or all registered keys are exhausted.
        Advances the internal cursor on each successful call.
        """
        available = self.available_keys()
        if not available:
            return None
        if self._cursor >= len(self._keys) * 2:
            self._cursor = 0
        key = available[self._cursor % len(available)]
        self._cursor += 1
        return key


if __name__ == "__main__":
    # Spec tests
    assert ApiKeyRouter(['a', 'b', 'c']).total_keys() == 3
    assert ApiKeyRouter([]).total_keys() == 0
    assert ApiKeyRouter(['a', 'b']).is_exhausted('a') is False

    # Additional sanity checks for the new implementation
    r = ApiKeyRouter(['a', 'b', 'c'])
    assert r._keys == ['a', 'b', 'c']
    assert r._exhausted == set()
    assert r._cursor == 0

    r = ApiKeyRouter([])
    assert r._keys == [] and r._exhausted == set()
    assert r.next_key() is None

    r = ApiKeyRouter(['a', 'b', 'c'])
    assert r.next_key() == 'a'
    assert r.next_key() == 'b'
    assert r.next_key() == 'c'

    r = ApiKeyRouter(['a', 'b', 'c'])
    r.mark_exhausted('b')
    assert r.is_exhausted('b') is True
    assert r.is_exhausted('a') is False
    assert sorted(r.available_keys()) == ['a', 'c']
