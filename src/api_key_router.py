class ApiKeyRouter:
    def __init__(self, keys: list[str]):
        self._keys = list(keys)
        self._quota_exceeded: set[str] = set()

    def mark_quota_exceeded(self, key: str) -> None:
        if key in self._keys:
            self._quota_exceeded.add(key)

    def available_keys(self) -> list[str]:
        return [key for key in self._keys if key not in self._quota_exceeded]
