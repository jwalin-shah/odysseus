"""Compute the cumulative sum of pairwise (consecutive) absolute distances.

Given a sequence of numeric values, this module returns a list where each
entry is the cumulative sum of the absolute differences between consecutive
elements of the input sequence.  The result can be interpreted as the total
distance "traveled" along a 1-D path up to each step.
"""

from __future__ import annotations

from typing import Iterable, List, Union

Number = Union[int, float]


def pairwise_distance_cumulative_summer(sequence: Iterable[Number]) -> List[float]:
    """Return the cumulative sum of absolute differences between neighbours.

    Parameters
    ----------
    sequence:
        Any iterable yielding numeric values (``int`` or ``float``).

    Returns
    -------
    list[float]
        A list of length ``len(sequence) - 1`` where position ``i`` holds the
        sum of absolute differences from index ``0`` up to and including the
        pair ``(i, i + 1)``.  Returns an empty list when the input has fewer
        than two elements.

    Examples
    --------
    >>> pairwise_distance_cumulative_summer([1, 4, 7, 10])
    [3, 6, 9]
    >>> pairwise_distance_cumulative_summer([10, 7, 4, 1])
    [3, 6, 9]
    >>> pairwise_distance_cumulative_summer([5, 2])
    [3]
    >>> pairwise_distance_cumulative_summer([])
    []
    >>> pairwise_distance_cumulative_summer([42])
    []
    """
    # Guard against obviously invalid inputs early.
    if not hasattr(sequence, "__iter__"):
        raise TypeError(
            "pairwise_distance_cumulative_summer expects an iterable of numbers, "
            f"got {type(sequence).__name__}"
        )

    values = list(sequence)

    # Need at least two points to form a pair; otherwise the cumulative
    # distance is the empty sum.
    if len(values) < 2:
        return []

    result: List[float] = []
    cumulative = 0.0
    for left, right in zip(values, values[1:]):
        cumulative += abs(right - left)
        result.append(cumulative)

    return result


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    demo = [1, 4, 7, 10]
    print(f"Input:  {demo}")
    print(f"Output: {pairwise_distance_cumulative_summer(demo)}")