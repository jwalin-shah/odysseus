import heapq

class PriorityQueue:
    def __init__(self):
        self._queue = []
        self._index = 0

    def push(self, item, priority):
        heapq.heappush(self._queue, (priority, self._index, item))
        self._index += 1

    def pop(self):
        if self.is_empty():
            raise IndexError("pop from an empty priority queue")
        return heapq.heappop(self._queue)[-1]

    def peek(self):
        if self.is_empty():
            raise IndexError("peek from an empty priority queue")
        return self._queue[0][-1]

    def is_empty(self):
        return len(self._queue) == 0

    def size(self):
        return len(self._queue)

    def __len__(self):
        return len(self._queue)

    def __bool__(self):
        return bool(self._queue)