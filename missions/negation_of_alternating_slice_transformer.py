"""
negation_of_alternating_slice_transformer
=========================================

A small utility that takes a numeric sequence, splits it into ``num_slices``
consecutive (near-equal) chunks, and negates every other chunk
(1st, 3rd, 5th, ...).  The transformed chunks are then concatenated back
into a single list which is returned.

Example
-------
>>> negation_of_alternating_slice_transformer([1, 2, 3, 4, 5, 6, 7, 8], 2)
[-1, -2, -3, -4, 5, 6, 7, 8]
>>> negation_of_alternating_slice_transformer([1, 2, 3, 4, 5, 6, 7, 8], 4)
[-1, -2, 3, 4, -5, -6, 7, 8]
"""


def negation_of_alternating_slice_transformer(values, num_slices=2):
    """Split ``values`` into ``num_slices`` consecutive chunks and negate
    every other chunk (1st, 3rd, 5th, ...).

    Parameters
    ----------
    values : iterable of numbers
        The sequence to transform.  Will be materialised into a list.
    num_slices : int, optional
        How many consecutive chunks to split the sequence into.
        Defaults to ``2``.  Must be ``>= 1``.  Values larger than
        ``len(values)`` are silently capped to ``len(values)``.

    Returns
    -------
    list
        A new list containing the recombined, partially-negated sequence.

    Raises
    ------
    ValueError
        If ``num_slices`` is less than 1.
    """
    if not isinstance(num_slices, int):
        raise TypeError("num_slices must be an integer")
    if num_slices < 1:
        raise ValueError("num_slices must be at least 1")

    values = list(values)
    n = len(values)

    if n == 0:
        return []

    # Capping to n guarantees we never try to create empty chunks.
    num_slices = min(num_slices, n)

    base_size = n // num_slices
    remainder = n % num_slices  # extra element goes to the first slices

    result = []
    start = 0
    for i in range(num_slices):
        chunk_size = base_size + (1 if i < remainder else 0)
        chunk = values[start:start + chunk_size]
        start += chunk_size
        if i % 2 == 0:  # negate 1st, 3rd, 5th, ... chunk
            chunk = [-x for x in chunk]
        result.extend(chunk)

    return result


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    print(negation_of_alternating_slice_transformer([1, 2, 3, 4, 5, 6, 7, 8], 2))
    print(negation_of_alternating_slice_transformer([1, 2, 3, 4, 5, 6, 7, 8], 4))
    print(negation_of_alternating_slice_transformer([1, 2, 3, 4, 5, 6, 7, 8, 9], 3))
    print(negation_of_alternating_slice_transformer([], 2))
    print(negation_of_alternating_slice_transformer([42]))