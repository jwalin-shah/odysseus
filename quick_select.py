def kth_smallest(arr: list, k: int) -> any:
    """Return the kth smallest element of arr (1-indexed).

    Uses the quickselect algorithm with median-of-three pivot selection.
    Average time complexity is O(n); worst case is O(n^2).

    Args:
        arr: A non-empty list of comparable elements.
        k:   1-indexed position, where k=1 returns the minimum.

    Raises:
        ValueError: If k < 1 or k > len(arr).
    """
    if not isinstance(k, int):
        raise ValueError("k must be an integer")
    if k < 1 or k > len(arr):
        raise ValueError("k is out of range for the given array")

    arr = list(arr)  # avoid mutating the caller's list
    _quickselect(arr, 0, len(arr) - 1, k - 1)
    return arr[k - 1]


def _quickselect(arr: list, left: int, right: int, target: int) -> None:
    """In-place quickselect; arranges arr so that arr[target] is correct."""
    while left < right:
        # Median-of-three pivot: pick median of first, middle, last
        pivot_index = _median_of_three(arr, left, right)

        # Partition around the chosen pivot and get its final position
        pivot_index = _partition(arr, left, right, pivot_index)

        if target == pivot_index:
            return
        elif target < pivot_index:
            right = pivot_index - 1
        else:
            left = pivot_index + 1


def _median_of_three(arr: list, left: int, right: int) -> int:
    """Return the index of the median among arr[left], arr[mid], arr[right]."""
    mid = (left + right) // 2
    a, b, c = arr[left], arr[mid], arr[right]
    if a <= b <= c or c <= b <= a:
        return mid
    if b <= a <= c or c <= a <= b:
        return left
    return right


def _partition(arr: list, left: int, right: int, pivot_index: int) -> int:
    """Lomuto-style partition with the pivot moved to the right end first."""
    pivot_value = arr[pivot_index]
    # Move pivot to the end of the working range
    arr[pivot_index], arr[right] = arr[right], arr[pivot_index]
    store_index = left
    for i in range(left, right):
        if arr[i] < pivot_value:
            arr[store_index], arr[i] = arr[i], arr[store_index]
            store_index += 1
    # Move pivot to its final sorted position
    arr[store_index], arr[right] = arr[right], arr[store_index]
    return store_index