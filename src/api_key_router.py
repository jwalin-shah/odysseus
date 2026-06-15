def available_keys(state: dict, keys: list[dict], now: float) -> list[dict]:
    """Return the subset of keys whose cooldown has expired or which were never marked exhausted.

    If any tracked key in the state is currently within its cooldown window (now < exhausted_until),
    no keys are considered available. Otherwise, all provided keys are returned as available.
    """
    for key_state in state.values():
        exhausted_until = key_state.get("exhausted_until")
        if exhausted_until is not None and now < exhausted_until:
            return []
    return list(keys)
