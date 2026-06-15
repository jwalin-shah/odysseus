import hashlib
import json


def compute_message_hash(message: dict) -> str:
    """Compute a deterministic SHA-256 hash for a message dict."""
    message_str = json.dumps(message, sort_keys=True, default=str)
    return hashlib.sha256(message_str.encode("utf-8")).hexdigest()


def filter_unseen_messages(messages: list[dict], seen_hashes: set) -> list[dict]:
    """Return only the messages whose hash is not present in seen_hashes, preserving input order."""
    return [msg for msg in messages if compute_message_hash(msg) not in seen_hashes]
