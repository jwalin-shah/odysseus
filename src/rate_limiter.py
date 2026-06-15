import threading
import time


class TokenBucket:
    def __init__(self, rpm: int, capacity: int | None = None) -> None:
        self.rpm = rpm
        self.capacity = capacity if capacity is not None else rpm
        self._tokens = self.capacity
        self._lock = threading.Lock()
