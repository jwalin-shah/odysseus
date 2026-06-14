"""
Interleaved zip with fill sentinel.

This module provides a function that interleaves multiple iterables into a
single flat list, padding shorter iterables with a sentinel value.
"""


def interleaved_zip_with_fill_sentinel(*iterables, fillvalue=None):
    """
    Interleave elements from multiple iterables into a single flat list.

    The function takes a position-by-position approach: for each position
    starting at 0, it appends the element at that position from each
    iterable (in the order the iterables were given).  If an iterable is
    shorter than the longest one, ``fillvalue`` is used in its place.

    The process continues for as many positions as the longest iterable
    supplies.  The returned list is therefore ``max_length * n_iterables``
    elements long, where ``max_length`` is the length of the longest input
    and ``n_iterables`` is the number of iterables supplied.

    Args:
        *iterables: Variable number of iterables to interleave.
        fillvalue: The value to use when an iterable is exhausted at a
            given position.  Defaults to ``None``.

    Returns:
        list: A flat list containing the interleaved elements.

    Examples:
        >>> interleaved_zip_with_fill_sentinel([1, 2, 3], ['a', 'b', 'c'])
        [1, 'a', 2, 'b', 3, 'c']

        >>> interleaved_zip_with_fill_sentinel([1, 2, 3], ['a', 'b'], fillvalue='_')
        [1, 'a', 2, 'b', 3, '_']

        >>> interleaved_zip_with_fill_sentinel([1, 2], ['a', 'b', 'c'], fillvalue='_')
        [1, 'a', 2, 'b', '_', 'c']
    """
    if not iterables:
        return []

    # Materialize the iterables so we can determine their lengths and
    # access elements by index.  This guarantees well-defined behaviour
    # even when an iterable is empty from the start.
    lists = [list(it) for it in iterables]

    # If every supplied iterable is empty, the result is empty too.
    max_len = max((len(lst) for lst in lists), default=0)
    if max_len == 0:
        return []

    result = []
    for position in range(max_len):
        for lst in lists:
            if position < len(lst):
                result.append(lst[position])
            else:
                result.append(fillvalue)

    return result


__all__ = ["interleaved_zip_with_fill_sentinel"]