import hashlib
import json


def merge_new_hashes(cache: set, new_hashes: set) -> set:
    """Return the union of cache and new_hashes without mutating either input."""
    return cache | new_hashes


def compute_message_hash(message) -> str:
    """Return a stable hex digest for a single message."""
    payload = json.dumps(message, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def compute_message_hashes(messages: list) -> list:
    """Hash a batch of messages and return a list of hex digests in the same order as the input."""
    return [compute_message_hash(m) for m in messages]


assert compute_message_hashes([]) == []
assert len(compute_message_hashes([{"id": str(i)} for i in range(5)])) == 5
assert compute_message_hashes([{"id": "42"}])[0] == compute_message_hash({"id": "42"})
