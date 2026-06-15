from __future__ import annotations

class ApiKeyRouter:
    def __init__(self, keys: list[str]):
        self.keys = keys
        self.index = 0
        self.cooldown = set()

    def report_quota_error(self, key: str):
        self.cooldown.add(key)

    def get_key(self) -> str | None:
        if not self.keys:
            return None
        n = len(self.keys)
        for _ in range(n):
            key = self.keys[self.index]
            if key not in self.cooldown:
                self.index = (self.index + 1) % n
                return key
            else:
                self.index = (self.index + 1) % n
        return None
