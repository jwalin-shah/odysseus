class ApiKeyRouter:
    def __init__(self, keys: list[str]):
        self.keys = keys
        self.exhausted = set()
        self.index = 0

    def next_key(self) -> str | None:
        if not self.keys:
            return None

        if len(self.exhausted) >= len(self.keys):
            return None

        start = self.index
        while True:
            key = self.keys[self.index]
            self.index = (self.index + 1) % len(self.keys)
            if key not in self.exhausted:
                return key
            if self.index == start:
                return None

    def mark_quota_exceeded(self, key: str) -> None:
        self.exhausted.add(key)
