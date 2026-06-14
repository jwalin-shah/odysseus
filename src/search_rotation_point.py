from typing import List


def search_rotation_point(arr: List[int]) -> int:
    """
    Find the index of the rotation point in a rotated sorted array.

    The rotation point is the index of the smallest element in the array,
    i.e. the location at which the originally-sorted array was "cut" and
    the front half was moved to the back.  For an unrotated (already
    sorted) array the rotation point is index 0.

    The function uses a binary-search-style algorithm and therefore runs
    in O(log n) time on arrays of size n.

    Parameters
    ----------
    arr : list
        A list of comparable elements that was originally sorted in
        strictly ascending order and then rotated at some pivot.  The
        input is assumed to contain no duplicates.

    Returns
    -------
    int
        The index of the rotation point (smallest element), or ``-1``
        if the input array is empty.
    """
    # Edge case: empty array has no rotation point.
    if not arr:
        return -1

    left, right = 0, len(arr) - 1

    # If the first element is less than or equal to the last element,
    # the array is not rotated (or the rotation point is at index 0).
    if arr[left] <= arr[right]:
        return 0

    # Binary search for the rotation point.
    while left <= right:
        mid = (left + right) // 2

        # The rotation point is the place where the strictly ascending
        # order is broken: a[mid] is smaller than its predecessor.
        if mid > 0 and arr[mid] < arr[mid - 1]:
            return mid

        # Alternatively, a[mid] is larger than its successor, so the
        # rotation point is at mid + 1.
        if mid < len(arr) - 1 and arr[mid] > arr[mid + 1]:
            return mid + 1

        # Decide which half of the array still contains the rotation
        # point.  If the left half is sorted, the pivot must be in the
        # right half; otherwise it is in the left half.
        if arr[mid] >= arr[left]:
            left = mid + 1
        else:
            right = mid - 1

    # Should not be reached for a valid rotated sorted array.
    return -1


if __name__ == "__main__":  # pragma: no cover - simple manual demo
    examples = [
        [15, 18, 2, 3, 6, 12],
        [7, 9, 11, 12, 5],
        [1, 2, 3, 4, 5],
        [],
        [1],
        [2, 1],
    ]
    for ex in examples:
        print(f"{ex} -> rotation point index = {search_rotation_point(ex)}")