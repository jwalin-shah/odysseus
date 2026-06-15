import time
import threading


class TokenBucket:
    def __init__(self, rpm: int) -> None:
        self.capacity = rpm
        self.refill_rate = rpm / 60
        self.tokens = float(rpm)
        self.lock = threading.Lock()
