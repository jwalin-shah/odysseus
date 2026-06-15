import time
import threading


class TokenBucket:
    def __init__(self, capacity: int, rate: float = 1.0) -> None:
        self.capacity = float(capacity)
        self.rate = float(rate)
        self.tokens = float(capacity)
        self.last_refill = time.monotonic()
        self.lock = threading.Lock()

    def _refill(self, now: float) -> None:
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
        self.last_refill = now
