import time


class TokenBucket:
    def __init__(self, rpm: float, max_burst: float = float('inf')):
        self.rpm = float(rpm)
        self.max_burst = float(max_burst)
        self.rate = self.rpm / 60.0  # tokens per second
        self.tokens = float(max_burst)
        self.last_update = time.monotonic()

    def _refresh(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_update
        if elapsed > 0:
            self.tokens = min(self.max_burst, self.tokens + elapsed * self.rate)
            self.last_update = now

    def wait_time(self, tokens: float = 1.0) -> float:
        self._refresh()
        if self.tokens >= tokens:
            return 0.0
        deficit = tokens - self.tokens
        if self.rate <= 0:
            return float('inf')
        return deficit / self.rate
