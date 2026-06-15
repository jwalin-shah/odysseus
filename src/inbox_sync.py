def next_sync_cursor(messages: list[dict], cursor_field: str = "ts") -> object:
    if not messages:
        return None
    return max(msg[cursor_field] for msg in messages)
