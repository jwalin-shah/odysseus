import hashlib


def compute_message_hash(msg: dict) -> str:
    # Extract identifying fields, supporting common naming conventions
    msg_id = msg.get("id", "")
    sender = msg.get("from", msg.get("sender", ""))
    timestamp = msg.get("ts", msg.get("timestamp", ""))
    body = msg.get("body", "")
    
    # Concatenate fields in a deterministic order using a separator
    content = f"{msg_id}|{sender}|{timestamp}|{body}"
    
    # Compute SHA-256 hex digest
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
