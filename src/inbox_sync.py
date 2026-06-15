import hashlib
import json


def merge_new_hashes(cache: set, new_hashes: set) -> set:
    """Return the union of cache and new_hashes without mutating either input."""
    return cache | new_hashes


def compute_message_hash(msg: dict) -> str:
    """Compute a stable SHA256 hex digest over a message's identifying fields.

    Hashes only (id, sender, subject, body, timestamp) in a fixed, sorted
    order so that identical messages produce the same digest regardless of
    where those fields sit in the input dict or what other metadata is
    attached. Missing fields are treated as ``None`` and ignored-field
    metadata is dropped entirely.
    """
    fields = ("id", "sender", "subject", "body", "timestamp")
    canonical = {field: msg.get(field) for field in fields}
    serialized = json.dumps(canonical, sort_keys=True, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def load_hash_store(path: str) -> set:
    """Load a set of message hashes from a JSON file at path.

    Returns an empty set if the file is missing or contains invalid JSON.
    """
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return set()
    if isinstance(data, list):
        return set(data)
    return set()


assert len(compute_message_hash({"id": "1", "subject": "s", "body": "b", "sender": "a", "timestamp": 1})) == 64
assert compute_message_hash({"id": "1", "subject": "s"}) == compute_message_hash({"subject": "s", "id": "1", "noise": "x"})
assert compute_message_hash({"id": "1"}) != compute_message_hash({"id": "2"})
