def normalize_message_for_hash(message: dict) -> dict:
    return {
        'id': message['id'],
        'timestamp': message['timestamp'],
        'sender': message['sender'],
        'body': message['body']
    }
