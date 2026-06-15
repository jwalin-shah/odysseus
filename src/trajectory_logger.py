"""Trajectory logger utilities for normalizing chat message formats."""


def to_chat_completion_messages(messages: list[dict]) -> list[dict]:
    """Normalize internal message dicts to OpenAI-style chat completion format.

    Ensures every message dict contains explicit ``role`` and ``content`` keys.
    Existing values are preserved; missing ``content`` defaults to an empty
    string. Additional keys (e.g. ``tool_call_id``, ``name``) are retained.
    """
    normalized: list[dict] = []
    for msg in messages:
        new_msg = dict(msg)
        new_msg.setdefault("content", "")
        new_msg.setdefault("role", "")
        normalized.append(new_msg)
    return normalized
