import time
from typing import Callable, Optional


class CircuitBreaker:
    def __init__(self, fail_threshold: int, cooldown: float, time_func: Optional[Callable[[], float]] = None) -> None:
        self.fail_threshold = fail_threshold
        self.cooldown = cooldown
        self._time_func = time_func if time_func is not None else time.monotonic
        self._failures = 0
        self._opened_at: Optional[float] = None
        self.state = "closed"

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.fail_threshold and self.state != "open":
            self.state = "open"
            self._opened_at = self._time_func()
