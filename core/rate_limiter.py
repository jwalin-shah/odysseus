import threading
import time


class RateLimiter:
    """Token bucket rate limiter.

    Allows up to ``calls_per_second`` operations per second, with burst
    capacity of ``max(1, calls_per_second)`` tokens. Tokens replenish
    continuously based on elapsed wall-clock time.
    """

    def __init__(self, calls_per_second: float):
        if calls_per_second <= 0:
            raise ValueError("calls_per_second must be positive")
        self._rate = float(calls_per_second)
        self._burst = float(max(1, calls_per_second))
        self._tokens = self._burst
        self._last_update = time.monotonic()
        self._lock = threading.Lock()

    def _replenish(self) -> None:
        """Add tokens accrued since the last update, capped at ``burst``."""
        now = time.monotonic()
        elapsed = now - self._last_update
        if elapsed > 0:
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last_update = now

    def try_acquire(self) -> bool:
        """Attempt to take a token without blocking.

        Returns:
            True if a token was available and consumed, False otherwise.
        """
        with self._lock:
            self._replenish()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    def acquire(self) -> None:
        """Block (via ``time.sleep``) until a token becomes available, then take it."""
        while True:
            with self._lock:
                self._replenish()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                tokens_needed = 1.0 - self._tokens
                wait_time = tokens_needed / self._rate
            time.sleep(wait_time)