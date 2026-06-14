"""LRU Cache implementation using OrderedDict for O(1) get and put operations."""

from collections import OrderedDict


class LRUCache:
    """Least Recently Used (LRU) cache with O(1) get and put operations.

    Items are evicted in the order they were least recently accessed:
    every successful get or put marks the key as most recently used, and
    when the cache is at capacity the oldest (least recently used) entry
    is removed to make room for a new one.
    """

    def __init__(self, capacity: int) -> None:
        """Initialize the LRU cache with the given positive capacity.

        Args:
            capacity: The maximum number of items the cache can hold.

        Raises:
            ValueError: If capacity is not a positive integer.
        """
        if not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("Capacity must be a positive integer")
        self._capacity = capacity
        self._cache: "OrderedDict[int, int]" = OrderedDict()

    def get(self, key: int) -> int:
        """Return the value for ``key`` and mark it as most recently used.

        Args:
            key: The key to look up.

        Returns:
            The stored value, or ``-1`` if the key is not present.
        """
        if key not in self._cache:
            return -1
        # Promote the accessed entry to the "most recently used" end.
        self._cache.move_to_end(key)
        return self._cache[key]

    def put(self, key: int, value: int) -> None:
        """Insert or update ``key`` to ``value`` and evict the LRU entry if full.

        If the key already exists, its value is updated and the key is
        promoted to the most-recently-used position. If the key is new and
        the cache is at capacity, the least-recently-used entry is removed
        before inserting.

        Args:
            key: The key to insert or update.
            value: The value to associate with the key.
        """
        if key in self._cache:
            # Update existing entry and mark it as most recently used.
            self._cache.move_to_end(key)
        elif len(self._cache) >= self._capacity:
            # Evict the least recently used entry (the front of the OrderedDict).
            self._cache.popitem(last=False)
        self._cache[key] = value