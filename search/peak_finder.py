def find_peak(arr):
    """
    Find a peak element in the array using binary search.
    A peak element is one which is greater than or equal to its neighbors.
    Returns one valid peak (not necessarily the maximum).
    """
    if not arr:
        return None
    n = len(arr)
    if n == 1:
        return arr[0]
    # Check boundaries
    if arr[0] >= arr[1]:
        return arr[0]
    if arr[n - 1] >= arr[n - 2]:
        return arr[n - 1]
    # Binary search on the interior
    left, right = 1, n - 2
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] >= arr[mid - 1] and arr[mid] >= arr[mid + 1]:
            return arr[mid]
        elif arr[mid - 1] > arr[mid]:
            right = mid - 1
        else:
            left = mid + 1
    # Fallback (shouldn't be reached for non-empty arrays)
    return arr[0]


def peak_finder(arr):
    """
    Public-facing peak finder. Returns a peak element value
    from the input array, or None if the array is empty.
    """
    return find_peak(arr)


# Backwards-compatible alias used by some callers/tests.
peakFinder = find_peak
peak = find_peak