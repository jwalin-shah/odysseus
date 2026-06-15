def diff_new_hashes(remote_hashes: set, local_hashes: set) -> set:
    """Return the set difference of remote_hashes minus local_hashes.

    This represents newly seen message hashes that exist in the remote
    set but not in the local set.

    Args:
        remote_hashes: Set of message hashes from the remote source.
        local_hashes: Set of message hashes already known locally.

    Returns:
        A set containing hashes present in remote_hashes but not in local_hashes.
    """
    return remote_hashes - local_hashes
