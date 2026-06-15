import hashlib
import json


def compute_message_hash(message: dict) -> str:
    """Compute a stable SHA-256 hash for a message dictionary."""
    canonical = json.dumps(message, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def filter_new_messages(messages: list, known_hashes: set) -> list:
    """Return only messages whose hash is not already in known_hashes, preserving order."""
    return [
        msg
        for msg in messages
        if compute_message_hash(msg) not in known_hashes
    ]
