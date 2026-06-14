"""Bitwise AND reducer.

Reduces an iterable of integers by applying the bitwise AND operation
across all of its elements. This is the bitwise-AND analogue of
``functools.reduce(operator.and_, iterable)``.

Examples
--------
>>> bitwise_and_reducer([12, 10, 6])
0
>>> bitwise_and_reducer([15, 7, 3])
3
>>> bitwise_and_reducer([42])
42
"""


def bitwise_and_reducer(values):
    """Return the bitwise AND of every value in *values*.

    Parameters
    ----------
    values : iterable of int
        The integers to combine. Any iterable (list, tuple, generator, ...)
        is accepted.

    Returns
    -------
    int
        The bitwise AND of all elements. If the iterable contains a single
        element, that element is returned unchanged.

    Raises
    ------
    ValueError
        If ``values`` is empty.
    TypeError
        If any element is not an integer (or a type supporting ``&``).
    """
    iterator = iter(values)

    try:
        first = next(iterator)
    except StopIteration:
        raise ValueError(
            "bitwise_and_reducer() requires at least one value; got empty iterable"
        )

    result = first
    for value in iterator:
        result &= value
        # Short-circuit: once the running AND is zero, every further AND
        # will keep it zero, so we can return early.
        if result == 0:
            return 0

    return result