def occurrence_count(haystack, needle):
    """Count the number of times needle appears in haystack.

    Overlapping occurrences are counted. Works with strings, lists, and tuples.
    Returns 0 for None inputs, empty needle, or when needle is longer than haystack.
    """
    if haystack is None or needle is None:
        return 0

    try:
        n = len(needle)
        m = len(haystack)
    except TypeError:
        return 0

    if n == 0 or m < n:
        return 0

    # String search: use find for efficiency, support overlapping matches
    if isinstance(haystack, str) and isinstance(needle, str):
        count = 0
        start = 0
        while True:
            idx = haystack.find(needle, start)
            if idx == -1:
                break
            count += 1
            start = idx + 1  # overlap by 1 character
        return count

    # Sequence search (list, tuple, etc.) - check consecutive subsequences
    count = 0
    for i in range(m - n + 1):
        match = True
        for j in range(n):
            # Using != correctly handles None elements
            if haystack[i + j] != needle[j]:
                match = False
                break
        if match:
            count += 1
    return count