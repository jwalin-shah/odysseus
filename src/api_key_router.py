def acquire_next_key(state: dict, keys: list[dict], now: float) -> dict | None:
    available = []
    for key in keys:
        key_id = key["id"]
        key_state = state.get(key_id, {})
        if key_state.get("exhausted_until", 0.0) <= now:
            available.append(key)

    if not available:
        return None

    cursor = state.get("cursor", 0)
    selected = available[cursor % len(available)]
    state["cursor"] = cursor + 1

    return selected
