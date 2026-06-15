import time

class ApiKeyRouter:
    def __init__(self, keys):
        self.keys = list(keys)
        self._cooldown_until = {}
        self._cooldown_duration = 60.0

    def report_quota_error(self, key):
        if key in self.keys:
            self._cooldown_until[key] = time.time() + self._cooldown_duration

    def available_count(self) -> int:
        now = time.time()
        available = 0
        for key in self.keys:
            if key not in self._cooldown_until or self._cooldown_until[key] <= now:
                available += 1
        return available
