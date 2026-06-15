def mark_key_exhausted(state: dict, key_id: str, cooldown_seconds: float, now: float) -> None:
    """Record that a key is exhausted until now+cooldown_seconds so the router skips it."""
    if key_id not in state:
        state[key_id] = {}
    state[key_id]["exhausted_until"] = now + cooldown_seconds
    state[key_id]["failures"] = state[key_id].get("failures", 0) + 1
