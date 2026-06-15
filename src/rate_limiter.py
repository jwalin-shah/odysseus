import time
import threading


class TokenBucket:
    def __init__(self, rpm: int) -> None:
        self.capacity = rpm
        self.refill_rate = rpm / 60
        self.tokens = float(rpm)
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        return None


assert TokenBucket(60)._refill() is None
assert 0.0 <= TokenBucket(60).tokens <= TokenBucket(60).capacity
