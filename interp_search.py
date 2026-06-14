"""Interpolation search implementation.

Provides a single public function :func:`interp_search` that locates a
``key`` inside a *sorted* numerically-valued sequence using the classic
interpolation-search algorithm.  It returns the index of the first
matching element when the value exists and ``-1`` otherwise.
"""


def interp_search(arr, key):
    """Locate ``key`` in the sorted sequence ``arr`` using interpolation search.

    Parameters
    ----------
    arr : sequence[float|int]
        A sorted (ascending) sequence of numbers.  The sequence is treated
        as a list internally; passing a generator or other one-shot
        iterator will exhaust it.
    key : int | float
        The value to search for.

    Returns
    -------
    int
        The index of ``key`` inside ``arr`` if it is present, otherwise
        ``-1``.  When the array contains duplicates, the index of *some*
        occurrence is returned (the first one the algorithm happens to
        probe).

    Notes
    -----
    Interpolation search performs in expected :math:`O(\\log\\log n)` time
    for uniformly distributed data, but degrades to :math:`O(n)` in the
    worst case (e.g. exponentially growing values).  The function performs
    explicit bounds checking so that:

    * empty inputs return ``-1``;
    * keys outside the value range return ``-1``;
    * uniform arrays (which would otherwise divide by zero) are handled
      correctly via a linear-style fallback.
    """
    # Convert to list so the function accepts any indexable sequence and
    # so ``len()`` / indexing are O(1).
    try:
        arr = list(arr)
    except TypeError:
        raise TypeError("arr must be an iterable of comparable numbers")

    n = len(arr)
    if n == 0:
        return -1

    low = 0
    high = n - 1

    # Fast path for a single-element array.
    if low == high:
        return low if arr[low] == key else -1

    while low <= high and key >= arr[low] and key <= arr[high]:
        # If the bounds have collapsed to a single position, this is it.
        if arr[low] == arr[high]:
            if arr[low] == key:
                return low
            return -1

        # Compute the estimated probe position.  Using floor division keeps
        # the result an int index even when the values are floats.
        try:
            pos = low + int((key - arr[low]) * (high - low) //
                            (arr[high] - arr[low]))
        except ZeroDivisionError:
            # Defensive: arr[low] == arr[high] already handled above, but
            # floats that compare equal can still differ in magnitude.
            pos = low

        # Guard against an out-of-range estimate (can happen with
        # non-uniform distributions).
        if pos < low:
            pos = low
        elif pos > high:
            pos = high

        if arr[pos] == key:
            return pos
        if arr[pos] < key:
            low = pos + 1
        else:
            high = pos - 1

    return -1


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    sample = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    for target in (10, 55, 90, 100, -5):
        print(target, "->", interp_search(sample, target))