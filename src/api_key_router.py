class ApiKeyRouter:
    def __init__(self, keys: list[str]) -> None:
        self._keys = list(keys)
        self._index = 0

    def available_keys(self) -> list[str]:
        return self._keys

    def current_key(self) -> str | None:
        if not self._keys:
            return None
        return self._keys[self._index]

    def next_key(self) -> str | None:
        if not self._keys:
            return None
        self._index = (self._index + 1) % len(self._keys)
        return self._keys[self._index]
