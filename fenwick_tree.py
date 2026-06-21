"""Fenwick Tree (Binary Indexed Tree) for prefix sums."""
from __future__ import annotations


class FenwickTree:
    def __init__(self, n: int):
        self.n = n
        self._tree = [0] * (n + 1)

    def update(self, i: int, delta: int) -> None:
        """Add delta to position i (1-indexed)."""
        # ODYSSEUS-ALGO-CRASH: refuse out-of-range and non-positive
        # indices. Without the guard `i <= 0`, `update(0, ...)` and
        # `update(-1, ...)` would silently enter an infinite loop
        # because `i & (-i)` is 0 for non-positive i, so `i += 0` never
        # advances past the while condition.
        if i < 1:
            raise ValueError(f"FenwickTree.update: i must be >= 1, got {i}")
        if i > self.n:
            raise IndexError(f"FenwickTree.update: i={i} exceeds n={self.n}")
        while i <= self.n:
            self._tree[i] += delta
            i += i & (-i)

    def prefix_sum(self, i: int) -> int:
        """Prefix sum [1..i] (1-indexed)."""
        # ODYSSEUS-ALGO-CRASH: previously raised IndexError from the
        # raw list access when `i > self.n` or `i <= 0`. The fix raises
        # explicitly with a clear message instead of relying on the
        # implicit IndexError from `_tree[i]`.
        if i < 0:
            raise IndexError(f"FenwickTree.prefix_sum: i must be >= 0, got {i}")
        if i > self.n:
            raise IndexError(f"FenwickTree.prefix_sum: i={i} exceeds n={self.n}")
        total = 0
        while i > 0:
            total += self._tree[i]
            i -= i & (-i)
        return total

    def range_sum(self, l: int, r: int) -> int:
        """Sum of [l..r] (1-indexed, inclusive)."""
        if l > r:
            return 0
        return self.prefix_sum(r) - self.prefix_sum(l - 1)

    # Aliases for compatibility
    def query(self, i: int) -> int:
        return self.prefix_sum(i)

    def range_query(self, l: int, r: int) -> int:
        return self.range_sum(l, r)

    @classmethod
    def from_array(cls, arr: list[int]) -> 'FenwickTree':
        """Build from 0-indexed array in O(n)."""
        n = len(arr)
        ft = cls(n)
        for i, v in enumerate(arr):
            ft.update(i + 1, v)
        return ft
