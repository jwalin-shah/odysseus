import time
import threading


class TokenBucket:
    def __init__(self, rpm: int) -> None:
        self._capacity = float(rpm)
        self._tokens = float(rpm)
        self._refill_rate = float(rpm) / 60.0
        self._lock = threading.Lock()
        self._last_refill = time.monotonic()
