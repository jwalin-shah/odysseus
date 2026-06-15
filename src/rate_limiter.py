import time


class TokenBucket:
    def __init__(self, rpm: float, max_burst: float = None) -> None:
        self.rate: float = rpm / 60.0  # tokens per second
        self.capacity: float = float(max_burst) if max_burst is not None else float(rpm)
        self.tokens: float = self.capacity
        self.last_update: float = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_update
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now

    def try_acquire(self, tokens: float = 1.0) -> bool:
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False
