import hashlib
import json


def compute_message_hash(message: dict) -> str:
    """Compute a deterministic hash for a message."""
    message_str = json.dumps(message, sort_keys=True)
    return hashlib.sha256(message_str.encode('utf-8')).hexdigest()


def update_hash_cache(known_hashes: set, new_messages: list) -> set:
    """Return a new set containing the union of known_hashes and the hashes computed from new_messages."""
    new_hashes = {compute_message_hash(msg) for msg in new_messages}
    return known_hashes | new_hashes
