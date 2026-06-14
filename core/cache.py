"""Simple in-memory TTL cache with LRU eviction and thread safety."""
import threading
import time
from collections import OrderedDict
from functools import wraps


class TTLCache:
    """Thread-safe in-memory cache with per-item TTL and LRU eviction.

    Expired items are evicted lazily on access (get/set). When the cache
    exceeds maxsize, the least recently used item is removed.
    """

    def __init__(self, maxsize: int, ttl_seconds: float):
        if maxsize <= 0:
            raise ValueError("maxsize must be positive")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.maxsize = maxsize
        self.ttl_seconds = ttl_seconds
        self._data = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        """Return the cached value for key, or None if missing/expired."""
        with self._lock:
            if key not in self._data:
                return None
            value, expiry = self._data[key]
            if time.monotonic() >= expiry:
                # Lazy eviction of expired item.
                del self._data[key]
                return None
            # Mark as recently used.
            self._data.move_to_end(key)
            return value

    def set(self, key, value):
        """Store value under key with the configured TTL."""
        with self._lock:
            expiry = time.monotonic() + self.ttl_seconds
            if key in self._data:
                # Refresh insertion order so it becomes most recently used.
                self._data.move_to_end(key)
            self._data[key] = (value, expiry)
            # Evict LRU items until within capacity.
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)

    def delete(self, key):
        """Remove key from the cache. No-op if key is absent."""
        with self._lock:
            self._data.pop(key, None)

    def clear(self):
        """Remove all items from the cache."""
        with self._lock:
            self._data.clear()

    def __len__(self):
        with self._lock:
            return len(self._data)

    def __contains__(self, key):
        return self.get(key) is not None


def lru_cache_with_ttl(maxsize: int = 128, ttl: float = 60.0):
    """Decorator that wraps a function with TTL-based LRU caching.

    Args:
        maxsize: Maximum number of entries to retain.
        ttl: Time-to-live for each cached result, in seconds.

    Returns:
        A decorator that caches the wrapped function's results.
    """
    cache = TTLCache(maxsize=maxsize, ttl_seconds=ttl)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build a hashable cache key. Sort kwargs for determinism.
            key = (args, tuple(sorted(kwargs.items())))
            cached = cache.get(key)
            if cached is not None:
                return cached
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        def cache_clear():
            cache.clear()

        wrapper.cache = cache
        wrapper.cache_clear = cache_clear
        return wrapper

    return decorator