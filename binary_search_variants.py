def binary_search(arr, target):
    """Standard binary search. Returns index of target or -1 if not found."""
    if not arr:
        return -1
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = left + (right - left) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1


def find_first(arr, target):
    """Find the first occurrence of target in a sorted array. Returns index or -1."""
    if not arr:
        return -1
    left, right = 0, len(arr) - 1
    result = -1
    while left <= right:
        mid = left + (right - left) // 2
        if arr[mid] == target:
            result = mid
            right = mid - 1
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return result


def find_last(arr, target):
    """Find the last occurrence of target in a sorted array. Returns index or -1."""
    if not arr:
        return -1
    left, right = 0, len(arr) - 1
    result = -1
    while left <= right:
        mid = left + (right - left) // 2
        if arr[mid] == target:
            result = mid
            left = mid + 1
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return result


def search_rotated(arr, target):
    """Search for target in a rotated sorted array (no duplicates). Returns index or -1."""
    if not arr:
        return -1
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = left + (right - left) // 2
        if arr[mid] == target:
            return mid
        # Determine which half is sorted
        if arr[left] <= arr[mid]:
            # Left half is sorted
            if arr[left] <= target < arr[mid]:
                right = mid - 1
            else:
                left = mid + 1
        else:
            # Right half is sorted
            if arr[mid] < target <= arr[right]:
                left = mid + 1
            else:
                right = mid - 1
    return -1


def find_peak(arr):
    """Find index of a peak element (no duplicates).
    A peak is arr[i] > arr[i-1] and arr[i] > arr[i+1].
    Assumes arr[-1] = arr[n] = -infinity. Returns index or -1 if empty."""
    if not arr:
        return -1
    left, right = 0, len(arr) - 1
    while left < right:
        mid = left + (right - left) // 2
        if arr[mid] > arr[mid + 1]:
            # Peak is in left half (including mid)
            right = mid
        else:
            # Peak is in right half
            left = mid + 1
    return left