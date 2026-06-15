import time


class ApiKeyRouter:
    def __init__(self, keys, cooldown_seconds=60.0):
        self._keys = set(keys)
        self._cooldown_seconds = cooldown_seconds
        self._error_times = {}

    def is_available(self, key: str) -> bool:
        if key not in self._keys:
            return False
        if key not in self._error_times:
            return True
        elapsed = time.time() - self._error_times[key]
        return elapsed >= self._cooldown_seconds

    def report_quota_error(self, key: str):
        if key in self._keys:
            self._error_times[key] = time.time()
