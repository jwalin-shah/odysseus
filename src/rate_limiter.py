import time
import threading


class TokenBucket:
    """A simple token bucket rate limiter.

    Tokens refill continuously at ``rpm / 60`` tokens per second up to
    ``capacity`` (defaults to ``rpm`` when ``max_burst`` is not supplied).
    """

    def __init__(self, rpm: float, max_burst: float | None = None) -> None:
        self.rpm: float = float(rpm)
        self.capacity: float = float(max_burst) if max_burst is not None else self.rpm
        self.tokens: float = self.capacity
        self.last_update: float = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_update
        if elapsed > 0:
            self.tokens = min(self.capacity, self.tokens + elapsed * (self.rpm / 60.0))
            self.last_update = now

    def try_consume(self, amount: float = 1.0) -> bool:
        with self._lock:
            self._refill()
            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False

    def time_to_available(self, amount: float = 1.0) -> float:
        """Seconds until ``amount`` tokens are available, or 0.0 if ready now."""
        with self._lock:
            self._refill()
            if self.tokens >= amount:
                return 0.0
            deficit = amount - self.tokens
            return deficit / (self.rpm / 60.0)


# Process-wide registry of buckets, keyed by name.
_buckets: dict[str, TokenBucket] = {}
_registry_lock = threading.Lock()


def get_bucket(name: str, rpm: float, max_burst: float | None = None) -> TokenBucket:
    """Return a process-singleton :class:`TokenBucket` for ``name``.

    The first call with a given ``name`` constructs a new bucket; subsequent
    calls return the same instance so that all callers share one throttle.
    ``rpm`` and ``max_burst`` are only honored on the first lookup.
    """
    bucket = _buckets.get(name)
    if bucket is not None:
        return bucket
    with _registry_lock:
        bucket = _buckets.get(name)
        if bucket is None:
            bucket = TokenBucket(rpm, max_burst)
            _buckets[name] = bucket
        return bucket
