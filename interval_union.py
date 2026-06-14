"""Compute the union of a collection of intervals.

Each interval is a 2-element sequence ``(start, end)`` with ``start <= end``.
The result is a list of non-overlapping, sorted tuples that cover every point
contained in any of the input intervals.
"""


def interval_union(intervals):
    """Return the union of ``intervals`` as a list of disjoint ``(start, end)`` tuples.

    Edge cases handled
    ------------------
    * ``None`` or empty input -> ``[]``.
    * Intervals with ``start > end`` are treated as invalid and skipped.
    * Malformed items (not 2-element indexable sequences) are silently ignored.
    * Touching intervals (e.g. ``[1, 3]`` and ``[3, 5]``) are merged, since they
      share the point ``3``.
    * Input ordering does not matter; the output is sorted by start.
    * Any iterable (including generators) is accepted.

    Parameters
    ----------
    intervals : iterable of 2-element sequences
        Each item is a ``(start, end)`` pair.

    Returns
    -------
    list of tuple
        Disjoint, sorted intervals that form the union of the input.
    """
    if intervals is None:
        return []

    valid = []
    for iv in intervals:
        try:
            s, e = iv[0], iv[1]
        except (TypeError, IndexError, KeyError, AttributeError, ValueError):
            continue
        if s is None or e is None:
            continue
        try:
            if s <= e:
                valid.append((s, e))
        except TypeError:
            # Non-comparable values (e.g. mixing str and int) -> skip.
            continue

    if not valid:
        return []

    valid.sort(key=lambda x: (x[0], x[1]))

    merged = [valid[0]]
    for start, end in valid[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            # Overlap or touch: extend the current interval if needed.
            if end > last_end:
                merged[-1] = (last_start, end)
        else:
            merged.append((start, end))

    return merged


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    samples = [
        [],
        [(1, 3)],
        [(1, 4), (2, 5), (7, 9), (8, 12)],
        [(1, 3), (3, 5), (10, 12)],
        [(5, 1), (1, 3)],
        [(-2, 0), (0, 3), (2, 5)],
    ]
    for s in samples:
        print(s, "->", interval_union(s))