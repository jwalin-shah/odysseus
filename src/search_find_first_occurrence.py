"""Find the index of the first occurrence of a pattern in a text.

This module provides :func:`search_find_first_occurrence`, a small utility
that mirrors the behaviour of ``str.find`` while also handling a few
edge-cases the caller may encounter (e.g. ``None`` arguments, empty
pattern, or non-string inputs).
"""

from __future__ import annotations

from typing import Any


def search_find_first_occurrence(text: Any, pattern: Any) -> int:
    """Return the lowest index of ``pattern`` in ``text``.

    Parameters
    ----------
    text : str
        The haystack to search through.
    pattern : str
        The needle to search for.

    Returns
    -------
    int
        The 0-based index of the first occurrence of ``pattern`` inside
        ``text``.  Returns ``-1`` if the pattern is not present.  An
        empty ``pattern`` is considered to occur at index ``0``.

    Notes
    -----
    * If either ``text`` or ``pattern`` is ``None``, ``-1`` is returned.
    * If either ``text`` or ``pattern`` is not a string instance, a
      :class:`TypeError` is raised.
    """
    if text is None or pattern is None:
        return -1

    if not isinstance(text, str):
        raise TypeError(
            f"text must be a str, got {type(text).__name__!r}"
        )
    if not isinstance(pattern, str):
        raise TypeError(
            f"pattern must be a str, got {type(pattern).__name__!r}"
        )

    # By definition an empty pattern is found at the very start of the
    # haystack, matching the behaviour of ``str.find``.
    if pattern == "":
        return 0

    return text.find(pattern)