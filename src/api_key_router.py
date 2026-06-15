import time


class ApiKeyRouter:
    DEFAULT_COOLDOWN_SECONDS = 60

    def __init__(self, keys):
        self._keys = list(keys)
        self._quota_errors = {}

    def report_quota_error(self, key):
        self._quota_errors[key] = time.time() + self.DEFAULT_COOLDOWN_SECONDS

    def reset(self, key: str) -> None:
        self._quota_errors.pop(key, None)

    def is_available(self, key: str) -> bool:
        if key not in self._quota_errors:
            return True
        return time.time() >= self._quota_errors[key]

    def available_count(self) -> int:
        return sum(1 for key in self._keys if self.is_available(key))

    def get_key(self):
        for key in self._keys:
            if self.is_available(key):
                return key
        return None
