import time
import threading


class TokenBucket:
    def __init__(self, rpm: float) -> None:
        self.rpm = float(rpm)
        self.capacity = 1.0
        self.refill_rate = rpm / 60
        self.tokens = 1.0
        self.lock = threading.Lock()


# Tests
assert TokenBucket(60).rpm == 60
assert TokenBucket(60).tokens == 1.0
assert TokenBucket(30).capacity == 1.0
