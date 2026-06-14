"""Run-length encoding utilities.

`run_length_pack` performs a simple run-length encoding of an iterable
of hashable (or at least equality-comparable) items, returning a list
of ``(value, count)`` tuples for each maximal run of consecutive
identical values.
"""


def run_length_pack(data):
    """Pack consecutive duplicates in *data* into ``(value, count)`` tuples.

    Parameters
    ----------
    data : iterable or None
        The input sequence to encode. Strings, lists, tuples, and any
        other iterable are supported. ``None`` is treated as the empty
        sequence.

    Returns
    -------
    list[tuple]
        A list of ``(value, count)`` tuples. An empty input (or ``None``)
        yields ``[]``.

    Examples
    --------
    >>> run_length_pack("aaabbc")
    [('a', 3), ('b', 2), ('c', 1)]
    >>> run_length_pack([1, 1, 2, 3, 3])
    [(1, 2), (2, 1), (3, 2)]
    >>> run_length_pack("")
    []
    """
    if data is None:
        return []

    iterator = iter(data)
    try:
        current = next(iterator)
    except StopIteration:
        return []

    result = []
    count = 1
    for item in iterator:
        if item == current:
            count += 1
        else:
            result.append((current, count))
            current = item
            count = 1
    result.append((current, count))
    return result


def run_length_unpack(packed):
    """Inverse of :func:`run_length_pack`.

    Given a list of ``(value, count)`` pairs, return a list with each
    value repeated the specified number of times.

    >>> run_length_unpack([('a', 3), ('b', 2)])
    ['a', 'a', 'a', 'b', 'b']
    """
    if not packed:
        return []
    out = []
    for value, count in packed:
        if count < 0:
            raise ValueError("count must be non-negative")
        out.extend([value] * count)
    return out


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    samples = [
        "",
        "a",
        "aaaa",
        "abcd",
        "aaabbc",
        "ababab",
        [1, 1, 2, 3, 3, 3, 4],
        (1, 1, 2, 2, 2, 3),
    ]
    for s in samples:
        packed = run_length_pack(s)
        print(f"{s!r} -> {packed}")