"""Pure-stdlib slice of MedianFinder used by the algo-crash regression tests.

The full median_finder module imports `sortedcontainers.SortedList` for
the sliding-window helper. That dependency is unavailable in the test
env; the heap-based streaming median is stdlib-only and exercises the
fixed find_median path.
"""
from __future__ import annotations

import heapq


class MedianFinder:
    def __init__(self):
        self._lo: list[int] = []
        self._hi: list[int] = []

    def add_num(self, num: int) -> None:
        heapq.heappush(self._lo, -num)
        heapq.heappush(self._hi, -heapq.heappop(self._lo))
        if len(self._hi) > len(self._lo):
            heapq.heappush(self._lo, -heapq.heappop(self._hi))

    def find_median(self) -> float:
        if not self._lo and not self._hi:
            from statistics import StatisticsError
            raise StatisticsError("find_median of empty MedianFinder")
        if len(self._lo) > len(self._hi):
            return float(-self._lo[0])
        return (-self._lo[0] + self._hi[0]) / 2.0
