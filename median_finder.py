"""Streaming median and sliding window median."""
from __future__ import annotations
import heapq
from sortedcontainers import SortedList


class MedianFinder:
    def __init__(self):
        self._lo: list[int] = []  # max-heap (negated)
        self._hi: list[int] = []  # min-heap

    def add_num(self, num: int) -> None:
        heapq.heappush(self._lo, -num)
        heapq.heappush(self._hi, -heapq.heappop(self._lo))
        if len(self._hi) > len(self._lo):
            heapq.heappush(self._lo, -heapq.heappop(self._hi))

    def find_median(self) -> float:
        # ODYSSEUS-ALGO-CRASH: previously raised IndexError from the
        # unconditional `-self._lo[0]` access when both heaps were
        # empty. Mirror `statistics.median` and raise StatisticsError.
        if not self._lo and not self._hi:
            from statistics import StatisticsError
            raise StatisticsError("find_median of empty MedianFinder")
        if len(self._lo) > len(self._hi):
            return float(-self._lo[0])
        return (-self._lo[0] + self._hi[0]) / 2.0


def sliding_window_median(nums: list[int], k: int) -> list[float]:
    """Sliding window median using SortedList."""
    sl = SortedList()
    result = []
    for i, x in enumerate(nums):
        sl.add(x)
        if i >= k:
            sl.remove(nums[i - k])
        if i >= k - 1:
            if k % 2:
                result.append(float(sl[k // 2]))
            else:
                result.append((sl[k // 2 - 1] + sl[k // 2]) / 2.0)
    return result
