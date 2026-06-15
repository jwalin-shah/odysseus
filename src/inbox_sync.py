import hashlib
import json


def compute_message_hash(message: dict) -> str:
    """Compute a deterministic SHA-256 hash for a message dictionary."""
    # Serialize the message to a JSON string with sorted keys for determinism
    message_str = json.dumps(message, sort_keys=True, default=str)
    return hashlib.sha256(message_str.encode('utf-8')).hexdigest()


def filter_new_messages(messages: list, seen_hashes: set) -> list:
    """Return only the messages whose computed hash is not present in the seen_hashes set."""
    return [msg for msg in messages if compute_message_hash(msg) not in seen_hashes]
