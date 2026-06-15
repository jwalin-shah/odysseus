import time


class TokenBucket:
    def __init__(self, rpm, max_burst=None):
        self.rpm = rpm
        self.capacity = max_burst if max_burst is not None else rpm
        self.tokens = float(self.capacity)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rpm / 60.0)
        self._last_refill = now
