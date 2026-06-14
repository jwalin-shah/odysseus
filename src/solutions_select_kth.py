"""Quickselect: find the k-th smallest element of a sequence.

The implementation uses an iterative Lomuto-partition quickselect with a
randomised pivot, giving average O(n) time and O(1) extra space while
guaranteeing that the caller's input is left untouched.
"""
from __future__ import annotations

import random
from typing import Any, Sequence


def solutions_select_kth(arr: Sequence, k: int) -> Any:
    """Return the k-th smallest element of ``arr`` (0-indexed).

    Parameters
    ----------
    arr:
        A non-empty sequence of mutually comparable elements.
    k:
        0-indexed position to return. ``k == 0`` returns the minimum and
        ``k == len(arr) - 1`` returns the maximum.

    Returns
    -------
    The k-th smallest element of ``arr``.

    Raises
    ------
    ValueError
        If ``arr`` is empty.
    IndexError
        If ``k`` is negative or not smaller than ``len(arr)``.
    """
    n = len(arr)
    if n == 0:
        raise ValueError("Cannot select from an empty sequence")
    if not isinstance(k, int) or isinstance(k, bool):
        raise TypeError(f"k must be an int, got {type(k).__name__}")
    if k < 0 or k >= n:
        raise IndexError(
            f"k={k} is out of bounds for sequence of length {n}"
        )

    # Copy so we can swap freely without disturbing the caller's data.
    nums = list(arr)

    lo, hi = 0, n - 1
    while True:
        if lo == hi:
            return nums[lo]

        # Randomised pivot avoids the O(n^2) worst case on sorted / nearly
        # sorted input and on adversarial inputs.
        pivot_idx = random.randint(lo, hi)
        nums[pivot_idx], nums[hi] = nums[hi], nums[pivot_idx]
        pivot = nums[hi]

        # Lomuto partition: elements strictly less than ``pivot`` end up at
        # indices [lo .. store-1]; the pivot lands at ``store``.
        store = lo
        for i in range(lo, hi):
            if nums[i] < pivot:
                if i != store:
                    nums[store], nums[i] = nums[i], nums[store]
                store += 1
        nums[store], nums[hi] = nums[hi], nums[store]

        if k == store:
            return nums[store]
        if k < store:
            hi = store - 1
        else:
            lo = store + 1