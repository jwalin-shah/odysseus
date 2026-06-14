"""Find the first occurrence of a needle in a haystack.

This module provides a single function, :func:`find_first_occurrence`, that
locates the index of the first occurrence of a *needle* inside a *haystack*.
The function works uniformly for strings and for arbitrary indexable
sequences (lists, tuples, ...), returning ``-1`` when the needle cannot be
found.  The semantics mirror the well-known behaviour of ``str.find`` so the
two can be used interchangeably for text data.
"""

from __future__ import annotations

from typing import Any, Sequence


def find_first_occurrence(haystack: Any, needle: Any) -> int:
    """Return the index of the first occurrence of ``needle`` in ``haystack``.

    Parameters
    ----------
    haystack:
        The sequence to search inside.  Can be a :class:`str`, :class:`list`,
        :class:`tuple` or any other object that supports ``len`` and slicing.
    needle:
        The pattern to search for.  Must be of the same type as ``haystack``
        (i.e. a string inside a string, a list inside a list, etc.).

    Returns
    -------
    int
        The zero-based index of the first occurrence of ``needle`` inside
        ``haystack``.  Returns ``-1`` when ``needle`` is not present.

    Notes
    -----
    The behaviour follows ``str.find``:

    * An empty ``needle`` is considered to be found at position ``0``.
    * If ``haystack`` is empty (or shorter than ``needle``) the result is
      ``-1``.
    * For string inputs the efficient built-in :meth:`str.find` is used;
      for other sequence types a straightforward linear scan is performed.

    Examples
    --------
    >>> find_first_occurrence("hello world", "world")
    6
    >>> find_first_occurrence([1, 2, 3, 4], [2, 3])
    1
    >>> find_first_occurrence("hello", "xyz")
    -1
    >>> find_first_occurrence("abc", "")
    0
    """
    # ``len`` is used for the size checks; it works for strings, bytes,
    # lists, tuples, ranges and any object implementing ``__len__``.
    try:
        haystack_len = len(haystack)
        needle_len = len(needle)
    except TypeError:
        raise TypeError(
            "haystack and needle must support len() "
            f"(got {type(haystack).__name__} and {type(needle).__name__})"
        )

    # An empty needle is conventionally found at position 0, matching the
    # behaviour of ``str.find``.
    if needle_len == 0:
        return 0

    # If the haystack is empty, or the needle is longer than the haystack,
    # there is no possible match.
    if haystack_len == 0 or needle_len > haystack_len:
        return -1

    # Fast path for strings: delegate to the C implementation.
    if isinstance(haystack, str) and isinstance(needle, str):
        return haystack.find(needle)

    # Generic sequence search.  We compare slices of length ``needle_len``
    # starting at each valid position.
    limit = haystack_len - needle_len + 1
    for start in range(limit):
        if haystack[start:start + needle_len] == needle:
            return start

    return -1


__all__ = ["find_first_occurrence"]


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    # A few quick examples when running the module directly.
    assert find_first_occurrence("hello world", "world") == 6
    assert find_first_occurrence([1, 2, 3, 4, 5], [2, 3]) == 1
    assert find_first_occurrence("hello", "xyz") == -1
    assert find_first_occurrence("abc", "") == 0
    assert find_first_occurrence("", "abc") == -1
    assert find_first_occurrence((1, 2, 3), (2, 3)) == 1
    print("All smoke tests passed.")