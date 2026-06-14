"""Reverse elements of a sequence in fixed-size windows.

Given a sequence and a positive window size ``k``, ``reverse_window``
returns a new sequence in which every contiguous chunk of ``k`` elements
is reversed.  Any final chunk smaller than ``k`` is reversed as well.

Example
-------
>>> reverse_window([1, 2, 3, 4, 5, 6, 7], 3)
[3, 2, 1, 6, 5, 4, 7]
"""

from __future__ import annotations

from typing import Any, Iterable, List, Sequence


def reverse_window(data: Iterable[Any], k: int) -> List[Any]:
    """Return a list with elements of ``data`` reversed in windows of size ``k``.

    Parameters
    ----------
    data:
        Any iterable.  It is materialised into a list internally, so the
        original object is never mutated.
    k:
        Positive integer specifying the window size.  Must be ``>= 1``.

    Returns
    -------
    list
        A new list where each consecutive block of up to ``k`` elements
        is reversed.

    Raises
    ------
    TypeError
        If ``k`` is not an integer.
    ValueError
        If ``k`` is less than 1.
    """
    if not isinstance(k, int) or isinstance(k, bool):
        raise TypeError(f"window size must be an int, got {type(k).__name__}")
    if k < 1:
        raise ValueError(f"window size must be >= 1, got {k}")

    # Materialise once so the input iterable is not consumed twice and
    # so that we work on a stable copy.
    seq: List[Any] = list(data)

    out: List[Any] = []
    for start in range(0, len(seq), k):
        chunk = seq[start : start + k]
        # ``reversed`` returns an iterator; extending is efficient.
        out.extend(reversed(chunk))
    return out


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    sample = [1, 2, 3, 4, 5, 6, 7]
    print(reverse_window(sample, 3))