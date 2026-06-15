import time


class TokenBucket:
    def __init__(self, rpm: int, capacity: int = None):
        self.rpm = rpm
        self.capacity = capacity if capacity is not None else rpm
        self.tokens = float(self.capacity)
        self.last_refill = time.time()

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * (self.rpm / 60.0))
        self.last_refill = now
