def search_sort_inversion_counter(arr):
    """
    Count the number of inversions in an iterable.
    An inversion is a pair (i, j) with i < j and arr[i] > arr[j].
    Accepts any iterable (lists, tuples, generators, etc.).
    Uses a modified merge sort for O(n log n) time complexity.
    """
    # Convert to list to support arbitrary iterables (generators, tuples, etc.)
    arr = list(arr)

    def merge_sort_count(sub):
        if len(sub) <= 1:
            return sub, 0
        mid = len(sub) // 2
        left, left_inv = merge_sort_count(sub[:mid])
        right, right_inv = merge_sort_count(sub[mid:])
        merged, split_inv = _merge_count(left, right)
        return merged, left_inv + right_inv + split_inv

    def _merge_count(left, right):
        merged = []
        i = j = 0
        inv = 0
        while i < len(left) and j < len(right):
            if left[i] <= right[j]:
                merged.append(left[i])
                i += 1
            else:
                merged.append(right[j])
                # All remaining elements in left are greater than right[j]
                inv += len(left) - i
                j += 1
        merged.extend(left[i:])
        merged.extend(right[j:])
        return merged, inv

    _, count = merge_sort_count(arr)
    return count