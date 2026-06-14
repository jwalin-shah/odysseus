from collections import Counter


def stack_sorted_frequency_rainbow_popper(s):
    """
    Sort characters/items in the input by frequency in descending order,
    breaking ties by first appearance in the input.

    The name is whimsical: we treat the input as a "stack" we will "pop"
    after sorting by frequency — like a rainbow popper organizing colors
    by how often they appear.

    Args:
        s: Input string or any iterable of hashable items.

    Returns:
        A list of items sorted by descending frequency, with ties broken
        by the order of first appearance in the input.
    """
    # Edge case: empty input
    if s is None:
        return []

    # Materialize once so we can iterate twice (for frequency and first appearance)
    items = list(s)

    if not items:
        return []

    # Count frequencies
    freq = Counter(items)

    # Track the index of first appearance for each distinct item
    first_appearance = {}
    for i, ch in enumerate(items):
        if ch not in first_appearance:
            first_appearance[ch] = i

    # Sort keys by (-frequency, first_appearance_index)
    # This gives descending frequency, ascending first appearance for ties
    sorted_keys = sorted(
        freq.keys(),
        key=lambda ch: (-freq[ch], first_appearance[ch]),
    )

    # Build the result list by repeating each item by its frequency
    result = []
    for ch in sorted_keys:
        result.extend([ch] * freq[ch])

    return result