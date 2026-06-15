from collections import OrderedDict


def merge_seen_hashes(existing: set, new_hashes: set, max_size: int = 10000) -> set:
    """Merge new hashes into the existing set, evicting the oldest entries (FIFO) when exceeding max_size.

    Args:
        existing: The current set of seen hashes.
        new_hashes: New hashes to merge in.
        max_size: Maximum allowed size of the resulting set.

    Returns:
        A new set containing the merged hashes, with oldest entries evicted if size exceeds max_size.
    """
    # Use OrderedDict to maintain insertion order for FIFO eviction
    ordered = OrderedDict()
    for item in existing:
        ordered[item] = None

    # Add new hashes that are not already present (preserve order of existing items)
    for item in new_hashes:
        if item not in ordered:
            ordered[item] = None

    # Evict oldest entries (FIFO) until size is within max_size
    while len(ordered) > max_size:
        ordered.popitem(last=False)

    return set(ordered.keys())
