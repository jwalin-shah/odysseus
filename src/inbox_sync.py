import hashlib
import json


def compute_message_hash(message):
    """Compute a deterministic hash for a message dictionary."""
    return hashlib.sha256(
        json.dumps(message, sort_keys=True).encode()
    ).hexdigest()


def filter_new_messages(messages, seen):
    """Return only messages whose hash is not in seen, preserving order."""
    return [msg for msg in messages if compute_message_hash(msg) not in seen]
