def merge_new_hashes(cache: set, new_hashes: set) -> set:
    """Return the union of cache and new_hashes without mutating either input."""
    return cache | new_hashes
