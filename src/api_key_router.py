class ApiKeyRouter:
    def __init__(self, keys: list) -> None:
        self._keys = keys
        self._exhausted = set()
        self._cursor = 0
