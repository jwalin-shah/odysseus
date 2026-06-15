def prune_hash_cache(known: dict[str, str], max_entries: int) -> dict[str, str]:
    """Bound the size of the known-hashes cache.

    Keeps the most-recently-inserted ``max_entries`` entries from
    ``known``, preserving the dict's natural insertion order, to prevent
    unbounded growth on long-running syncs. Returns a new dict; the
    input is not modified.
    """
    if max_entries <= 0:
        return {}
    if len(known) <= max_entries:
        return dict(known)

    # Dict insertion order is guaranteed from Python 3.7+, so slicing
    # the items list from the end keeps the most recently inserted keys.
    items = list(known.items())
    return dict(items[-max_entries:])
