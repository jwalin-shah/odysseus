import hashlib
import json


def compute_message_hash(message: dict) -> str:
    """Compute a stable hash for a message dictionary."""
    message_str = json.dumps(message, sort_keys=True, default=str)
    return hashlib.sha256(message_str.encode("utf-8")).hexdigest()


def filter_new_messages(messages: list, seen_hashes: set) -> list:
    """Return the subset of messages whose hash is not in seen_hashes, preserving order."""
    return [msg for msg in messages if compute_message_hash(msg) not in seen_hashes]
