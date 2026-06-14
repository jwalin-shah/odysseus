"""Implementation of missions_list_transforms_interleaved_zip_with_fill_sentinel.

This module provides a function that behaves similarly to
:func:`itertools.zip_longest`, but accepts multiple iterables as positional
arguments and a ``fillvalue`` keyword argument used to pad the shorter
iterables so that the result has the length of the longest input iterable.

The function is purposely written from scratch (without relying on
``itertools.zip_longest``) so that the logic is transparent and easy to test.
"""

from __future__ import annotations

from typing import Any, Iterable, List, Tuple


def missions_list_transforms_interleaved_zip_with_fill_sentinel(
    *lists: Iterable[Any],
    fillvalue: Any = None,
) -> List[Tuple[Any, ...]]:
    """Interleave (zip) multiple iterables, padding shorter ones with *fillvalue*.

    The function takes any number of iterables and returns a list of tuples
    where the *i*-th tuple contains the *i*-th element of every input.  When
    an input has fewer than *i* elements, ``fillvalue`` is substituted for
    that position in the tuple.

    Parameters
    ----------
    *lists:
        Variable number of iterables to be zipped together.  Empty iterables
        are permitted; if **all** inputs are empty, the function returns an
        empty list.
    fillvalue:
        Sentinel value used to pad the shorter iterables.  Defaults to
        ``None``.  A dedicated sentinel object can be used when ``None`` is a
        legitimate data value.

    Returns
    -------
    list[tuple]
        A list whose length equals the length of the longest input.  Each
        element is a tuple of length ``len(lists)``.

    Examples
    --------
    >>> missions_list_transforms_interleaved_zip_with_fill_sentinel([1, 2, 3],
    ...                                                              [4, 5])
    [(1, 4), (2, 5), (3, None)]

    >>> missions_list_transforms_interleaved_zip_with_fill_sentinel(
    ...     [1, 2], [3, 4], [5, 6, 7], fillvalue=0,
    ... )
    [(1, 3, 5), (2, 4, 6), (0, 0, 7)]
    """
    # Convert every input to a list up front so that we can both:
    #   1. Determine the maximum length without consuming generators twice.
    #   2. Index into each list repeatedly without exhausting it.
    materialised: List[List[Any]] = [list(lst) for lst in lists]

    # Special-case: no iterables supplied -> empty result.
    if not materialised:
        return []

    # The result is as long as the longest input iterable.
    max_len = max(len(lst) for lst in materialised)

    # If every input is empty, ``max_len`` is 0 and the loop is skipped.
    result: List[Tuple[Any, ...]] = []
    for i in range(max_len):
        group = tuple(
            lst[i] if i < len(lst) else fillvalue
            for lst in materialised
        )
        result.append(group)

    return result


__all__ = ["missions_list_transforms_interleaved_zip_with_fill_sentinel"]