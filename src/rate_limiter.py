import time
import threading


class TokenBucket:
    def __init__(self, rpm: float) -> None:
        self.rpm = float(rpm)
        self.capacity = 1.0
        self.refill_rate = rpm / 60
        self.tokens = 1.0
        self.lock = threading.Lock()

    def wait_time(self) -> float:
        """Return the number of seconds the caller must wait for the next token; 0.0 if one is available right now."""
        with self.lock:
            if self.tokens >= 1.0:
                return 0.0
            deficit = 1.0 - self.tokens
            return deficit / self.refill_rate


# Tests
assert TokenBucket(60).rpm == 60
assert TokenBucket(60).tokens == 1.0
assert TokenBucket(30).capacity == 1.0
assert TokenBucket(60).wait_time() == 0.0
assert TokenBucket(60).wait_time() >= 0.0
