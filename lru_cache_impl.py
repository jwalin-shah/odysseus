"""LRU Cache implementation using OrderedDict for O(1) operations."""
from collections import OrderedDict
from threading import Lock


class LRUCache:
    """A thread-safe Least Recently Used (LRU) cache implementation."""

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be a positive integer")
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = Lock()

    def get(self, key):
        """Retrieve an item from the cache. Returns -1 if not present."""
        with self.lock:
            if key not in self.cache:
                return -1
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key, value):
        """Insert or update an item in the cache, evicting the LRU item if full."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            self.cache[key] = value
            if len(self.cache) > self.capacity:
                self.cache.popitem(last=False)

    def __repr__(self):
        return f"LRUCache(capacity={self.capacity}, size={len(self.cache)})"


if __name__ == "__main__":
    cache = LRUCache(2)
    cache.put(1, 1)
    cache.put(2, 2)
    assert cache.get(1) == 1
    cache.put(3, 3)
    assert cache.get(2) == -1
    cache.put(4, 4)
    assert cache.get(1) == -1
    assert cache.get(3) == 3
    assert cache.get(4) == 4
    print("All LRU cache tests passed.")