from collections import deque
from typing import List


def sliding_window_max(arr: List[int], k: int) -> List[int]:
    """Return list of maximums for each sliding window of size k.

    Uses a monotonic deque to achieve O(n) time complexity.

    Raises:
        ValueError: If k < 1 or k > len(arr).
    """
    if not arr:
        return []

    if k < 1 or k > len(arr):
        raise ValueError(
            f"k must be between 1 and {len(arr)} (inclusive), got {k}"
        )

    result: List[int] = []
    dq: deque[int] = deque()  # stores indices of elements, decreasing by value

    for i, num in enumerate(arr):
        # Remove indices whose corresponding values are less than the
        # current value. They can never become the maximum while this
        # element is in the window.
        while dq and arr[dq[-1]] < num:
            dq.pop()

        dq.append(i)

        # Remove the index at the front if it is outside the current window.
        if dq[0] <= i - k:
            dq.popleft()

        # Once we have processed at least k elements, record the maximum
        # (which is the value at the front of the deque).
        if i >= k - 1:
            result.append(arr[dq[0]])

    return result