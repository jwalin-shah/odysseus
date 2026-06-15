import hashlib
import json


def compute_message_hash(msg: dict) -> str:
    """Compute a stable SHA-256 hex digest over the canonical JSON of a message dict."""
    canonical_json = json.dumps(msg, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
