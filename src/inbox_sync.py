import hashlib
import json


def fingerprint_message(message: dict) -> str:
    """Compute a deterministic fingerprint for a message dict."""
    encoded = json.dumps(message, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def filter_new(messages: list, seen_hashes: set) -> tuple:
    """Partition messages into (new_messages, updated_seen_hashes).

    Excludes any message whose fingerprint is already present in
    ``seen_hashes``. ``updated_seen_hashes`` is the union of the input
    set and the fingerprints of the new messages.
    """
    new_messages = []
    updated_seen_hashes = set(seen_hashes)

    for message in messages:
        fp = fingerprint_message(message)
        if fp not in seen_hashes:
            new_messages.append(message)
            updated_seen_hashes.add(fp)

    return (new_messages, updated_seen_hashes)
