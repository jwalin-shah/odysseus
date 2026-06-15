def recover_expired_keys(state: dict, now: float) -> int:
    """Clear expired cooldown entries and return the number of keys recovered.

    For each entry in ``state``, if its associated info dict contains an
    ``exhausted_until`` value that is less than or equal to ``now``, the
    ``exhausted_until`` field is removed and the recovery counter is
    incremented by one.

    Args:
        state: Mapping of key identifiers to their metadata dictionaries.
        now: Current time (e.g., epoch seconds) used to evaluate expiry.

    Returns:
        The number of keys whose cooldown entries were cleared.
    """
    recovered = 0
    for key_info in state.values():
        if isinstance(key_info, dict) and "exhausted_until" in key_info:
            if key_info["exhausted_until"] <= now:
                del key_info["exhausted_until"]
                recovered += 1
    return recovered
