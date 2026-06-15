import hashlib
import json

def compute_message_hash(msg: dict) -> str:
    """
    Compute a stable SHA-256 hash of an inbox message from its identifying fields.
    
    The identifying fields are id, body, timestamp, and sender. The function accepts
    both standard field names (timestamp, sender) and common aliases (ts, from).
    
    Args:
        msg: A dictionary representing an inbox message.
    
    Returns:
        A 64-character hexadecimal string representing the SHA-256 hash.
    """
    # Extract identifying fields with fallback to common aliases
    identifying = {
        "id": msg.get("id"),
        "body": msg.get("body"),
        "timestamp": msg.get("timestamp", msg.get("ts")),
        "sender": msg.get("sender", msg.get("from"))
    }
    
    # Serialize to a deterministic JSON string
    serialized = json.dumps(identifying, sort_keys=True, default=str)
    
    # Compute SHA-256 hash
    hash_obj = hashlib.sha256(serialized.encode('utf-8'))
    return hash_obj.hexdigest()
