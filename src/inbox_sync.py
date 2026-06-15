import hashlib
import json


def compute_message_hash(message: dict) -> str:
    canonical = {
        'id': message.get('id', ''),
        'sender': message.get('sender', ''),
        'timestamp': message.get('timestamp', 0),
        'body': message.get('body', ''),
    }
    canonical_str = json.dumps(canonical, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()
