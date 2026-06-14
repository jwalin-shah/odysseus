"""Bloom filter - space-efficient probabilistic membership set."""
from __future__ import annotations

import hashlib
import math


class BloomFilter:
    def __init__(self, capacity: int, error_rate: float = 0.01):
        self.capacity = capacity
        self.error_rate = error_rate
        self._size = self._optimal_size(capacity, error_rate)
        self._k = self._optimal_k(self._size, capacity)
        self._bits = bytearray(math.ceil(self._size / 8))
        self._count = 0

    @staticmethod
    def _optimal_size(n: int, p: float) -> int:
        return max(1, math.ceil(-n * math.log(p) / (math.log(2) ** 2)))

    @staticmethod
    def _optimal_k(m: int, n: int) -> int:
        return max(1, round(m / n * math.log(2)))

    def _hashes(self, item: str) -> list[int]:
        results: list[int] = []
        for i in range(self._k):
            digest = hashlib.md5(f"{i}:{item}".encode()).hexdigest()
            results.append(int(digest, 16) % self._size)
        return results

    def _set_bit(self, pos: int) -> None:
        self._bits[pos // 8] |= 1 << (pos % 8)

    def _get_bit(self, pos: int) -> bool:
        return bool(self._bits[pos // 8] & (1 << (pos % 8)))

    def add(self, item: str) -> None:
        for pos in self._hashes(item):
            self._set_bit(pos)
        self._count += 1

    def might_contain(self, item: str) -> bool:
        return all(self._get_bit(pos) for pos in self._hashes(item))

    def false_positive_probability(self) -> float:
        if self._count == 0:
            return 0.0
        return (1 - math.exp(-self._k * self._count / self._size)) ** self._k

    def __len__(self) -> int:
        return self._count

    def __contains__(self, item: str) -> bool:
        return self.might_contain(item)
