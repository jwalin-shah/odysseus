def update_sync_cursor(state: dict, messages: list) -> dict:
    """Return a new state dict with last_sync_ts advanced to the maximum
    timestamp present in messages. If messages is empty, the state is
    returned unchanged (as a shallow copy)."""
    new_state = dict(state)
    if not messages:
        return new_state

    max_message_ts = max(m["ts"] for m in messages)
    current_ts = state.get("last_sync_ts")

    if current_ts is not None and current_ts > max_message_ts:
        new_state["last_sync_ts"] = current_ts
    else:
        new_state["last_sync_ts"] = max_message_ts

    return new_state
