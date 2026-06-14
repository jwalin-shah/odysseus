from collections import Counter


def missions_stack_sorted_frequency_rainbow_popper(stack):
    """
    Given a stack (list) of mission items, return the unique items sorted by
    frequency in descending order. Items with the same frequency are ordered
    by their first appearance in the stack (stable, position-based ordering).

    This is the "rainbow popper" behavior: items are extracted from the stack
    one frequency-group at a time, most frequent first, with ties resolved
    by original stack position.

    Parameters
    ----------
    stack : list
        A list of hashable items representing a mission stack.

    Returns
    -------
    list
        Unique items sorted by (frequency desc, first-position asc).
    """
    if not stack:
        return []

    # Count frequency of each item
    freq = Counter(stack)

    # Track the first position where each unique item appears
    position = {}
    for i, item in enumerate(stack):
        if item not in position:
            position[item] = i

    # Collect unique items preserving order of first appearance
    unique_items = list(position.keys())

    # Sort by frequency (descending), then by first position (ascending)
    unique_items.sort(key=lambda x: (-freq[x], position[x]))

    return unique_items