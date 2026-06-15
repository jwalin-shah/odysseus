import hashlib
import json


def compute_message_hash(message: dict) -> str:
    """Compute a deterministic SHA-256 hash for a message dictionary."""
    serialized = json.dumps(message, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode('utf-8')).hexdigest()


def hash_messages(messages: list) -> dict:
    """Build a dict mapping each message's hash to the message itself.

    Collapses duplicate messages that share a hash into a single entry.
    Later messages with the same hash overwrite earlier ones.
    """
    result = {}
    for message in messages:
        h = compute_message_hash(message)
        result[h] = message
    return result
