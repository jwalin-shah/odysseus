def quick_sort(arr):
    """Return a new sorted list using quick sort with median-of-three pivot."""
    result = list(arr)
    _quick_sort(result, 0, len(result) - 1)
    return result


def quick_sort_inplace(arr):
    """Sort the list in place using quick sort with median-of-three pivot."""
    if not arr:
        return
    _quick_sort(arr, 0, len(arr) - 1)


def partition(arr, lo, hi):
    """Partition arr[lo:hi+1] using median-of-three pivot. Returns pivot index."""
    mid = (lo + hi) // 2
    # Median-of-three: order arr[lo], arr[mid], arr[hi]
    if arr[lo] > arr[mid]:
        arr[lo], arr[mid] = arr[mid], arr[lo]
    if arr[lo] > arr[hi]:
        arr[lo], arr[hi] = arr[hi], arr[lo]
    if arr[mid] > arr[hi]:
        arr[mid], arr[hi] = arr[hi], arr[mid]
    # Move median to hi-1 as sentinel (saves one swap later)
    arr[mid], arr[hi] = arr[hi], arr[mid]
    pivot = arr[hi]
    i = lo - 1
    for j in range(lo, hi):
        if arr[j] <= pivot:
            i += 1
            arr[i], arr[j] = arr[j], arr[i]
    arr[i + 1], arr[hi] = arr[hi], arr[i + 1]
    return i + 1


def _quick_sort(arr, lo, hi):
    while lo < hi:
        if hi - lo < 16:
            _insertion_sort(arr, lo, hi)
            return
        p = partition(arr, lo, hi)
        # Tail-recursion optimization: recurse on smaller half, loop on larger
        if p - lo < hi - p:
            _quick_sort(arr, lo, p - 1)
            lo = p + 1
        else:
            _quick_sort(arr, p + 1, hi)
            hi = p - 1


def _insertion_sort(arr, lo, hi):
    for i in range(lo + 1, hi + 1):
        key = arr[i]
        j = i - 1
        while j >= lo and arr[j] > key:
            arr[j + 1] = arr[j]
            j -= 1
        arr[j + 1] = key