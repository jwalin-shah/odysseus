class ApiKeyManager:
    def __init__(self, keys):
        self.keys = list(keys)
        self.exhausted = set()
        self.current_index = 0

    def mark_exhausted(self, key):
        self.exhausted.add(key)

    def next_key(self) -> str:
        n = len(self.keys)
        for _ in range(n):
            key = self.keys[self.current_index]
            self.current_index = (self.current_index + 1) % n
            if key not in self.exhausted:
                return key
        raise RuntimeError("All API keys are exhausted")
