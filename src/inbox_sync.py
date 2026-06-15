import hashlib
import json


def compute_message_hash(message: dict) -> str:
    fields = {
        'id': message.get('id', ''),
        'sender': message.get('sender', ''),
        'timestamp': message.get('timestamp', ''),
        'body': message.get('body', ''),
    }
    content = json.dumps(fields, sort_keys=True)
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
