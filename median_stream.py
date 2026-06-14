import heapq

class MedianFinder:
    """
    Maintains a running median of a stream of numbers using two heaps.
    - max_heap (lower half): a max-heap implemented with negative values.
    - min_heap (upper half): a min-heap.
    Invariant: len(max_heap) >= len(min_heap) and len(max_heap) - len(min_heap) <= 1.
    """

    def __init__(self):
        self.max_heap = []  # lower half
        self.min_heap = []  # upper half

    def add_num(self, num):
        # Push to appropriate heap.
        if not self.max_heap or num <= -self.max_heap[0]:
            heapq.heappush(self.max_heap, -num)
        else:
            heapq.heappush(self.min_heap, num)

        # Rebalance so max_heap has the extra element when sizes differ.
        if len(self.max_heap) > len(self.min_heap) + 1:
            heapq.heappush(self.min_heap, -heapq.heappop(self.max_heap))
        elif len(self.min_heap) > len(self.max_heap):
            heapq.heappush(self.max_heap, -heapq.heappop(self.min_heap))

    def find_median(self):
        if len(self.max_heap) == len(self.min_heap):
            return (-self.max_heap[0] + self.min_heap[0]) / 2.0
        return -self.max_heap[0]


class MedianStream:
    """Convenience wrapper exposing a stream-like API."""

    def __init__(self):
        self._finder = MedianFinder()
        self._buffer = []

    def push(self, num):
        self._buffer.append(num)
        self._finder.add_num(num)

    def median(self):
        return self._finder.find_median()

    def values(self):
        return list(self._buffer)