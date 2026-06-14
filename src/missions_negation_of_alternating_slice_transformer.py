"""Implementation of missions_negation_of_alternating_slice_transformer.

Negates alternating elements (at even indices) in a numeric sequence.
"""


def missions_negation_of_alternating_slice_transformer(data):
    """Transform a sequence by negating elements at alternating (even) indices.

    For each element at an even index (0, 2, 4, ...), the value's sign is
    flipped (negated). Elements at odd indices are passed through unchanged.
    The original input is not mutated; a new list is returned.

    Args:
        data: An iterable sequence of numeric values (int or float).

    Returns:
        A new list with alternating (even-indexed) elements negated.

    Raises:
        TypeError: If ``data`` is not iterable or if any element is not
            a numeric type (int or float, excluding bool subclasses).
    """
    # Validate that input is iterable. enumerate() will raise TypeError
    # for non-iterables, but we make the message clearer.
    try:
        iterator = iter(data)
    except TypeError as exc:
        raise TypeError(
            f"Input is not iterable: {data!r}"
        ) from exc

    result = []
    for i, item in enumerate(iterator):
        # bool is a subclass of int; explicitly reject it to avoid surprises.
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise TypeError(
                f"Element at index {i} is not numeric: {item!r}"
            )
        if i % 2 == 0:
            result.append(-item)
        else:
            result.append(item)
    return result