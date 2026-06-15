import threading
from typing import Dict


class TokenBucket:
    """A simple token bucket for rate limiting."""
    
    def __init__(self, rpm: int):
        self.rpm = rpm
        self.capacity = rpm
        self.tokens = float(rpm)
        self.last_refill = 0.0
        self.lock = threading.Lock()
    
    def __repr__(self) -> str:
        return f"TokenBucket(name={self.name!r}, rpm={self.rpm})"


_buckets: Dict[str, TokenBucket] = {}
_buckets_lock = threading.Lock()


def get_bucket(name: str, rpm: int = 60) -> TokenBucket:
    """Return a process-wide shared TokenBucket for the given name.
    
    Creates the bucket on first access; subsequent calls with the same name
    return the same instance (singleton per name). The first call's rpm value
    is preserved; later calls with a different rpm are ignored.
    
    Args:
        name: Identifier for the bucket.
        rpm: Requests per minute (used only on first creation).
    
    Returns:
        The shared TokenBucket instance for this name.
    """
    # Fast path: already created
    bucket = _buckets.get(name)
    if bucket is not None:
        return bucket
    
    # Slow path: create under lock
    with _buckets_lock:
        # Double-checked locking
        bucket = _buckets.get(name)
        if bucket is None:
            bucket = TokenBucket(rpm)
            bucket.name = name
            _buckets[name] = bucket
        return bucket
