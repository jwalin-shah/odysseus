"""Range compression utility.

The `range_compressor` function takes an iterable of integers and collapses
consecutive numbers into compact inclusive ranges represented as ``(start, end)``
tuples.  Duplicate values are removed and the input does not need to be sorted.
"""

from __future__ import annotations

from typing import Iterable, List, Tuple


def range_compressor(numbers: Iterable[int]) -> List[Tuple[int, int]]:
    """Compress a sequence of integers into consecutive ranges.

    Given an iterable of integers, returns a sorted list of ``(start, end)``
    tuples where each tuple represents a run of consecutive integers
    (inclusive on both ends).  The input does not need to be sorted; duplicate
    values are removed automatically.

    Args:
        numbers: Any iterable of integers (list, tuple, set, generator, ...).

    Returns:
        A list of ``(start, end)`` tuples.  Singletons are represented as
        ``(value, value)``.

    Examples:
        >>> range_compressor([1, 2, 3, 5, 7, 8, 10])
        [(1, 3), (5, 5), (7, 8), (10, 10)]
        >>> range_compressor([])
        []
        >>> range_compressor([0, 1, 2, 3, 4])
        [(0, 4)]
    """
    # Remove duplicates and sort.  ``sorted`` will raise ``TypeError`` on
    # heterogeneous / non-comparable inputs, which is the desired behaviour.
    try:
        unique = sorted(set(numbers))
    except TypeError as exc:  # pragma: no cover - defensive
        raise TypeError(
            "range_compressor requires an iterable of comparable integers"
        ) from exc

    if not unique:
        return []

    ranges: List[Tuple[int, int]] = []
    start = unique[0]
    end = unique[0]

    for num in unique[1:]:
        if num == end + 1:
            # Extend the current run.
            end = num
        else:
            # Close the current run and begin a new one.
            ranges.append((start, end))
            start = num
            end = num

    # Append the final run.
    ranges.append((start, end))
    return ranges


if __name__ == "__main__":  # pragma: no cover - manual demo
    demo_inputs = [
        [1, 2, 3, 5, 7, 8, 10],
        [],
        [5],
        [0, 1, 2, 3, 4],
        [1, 3, 5, 7, 9],
        [-3, -2, -1, 0, 1, 2],
    ]
    for sample in demo_inputs:
        print(f"{sample} -> {range_compressor(sample)}")