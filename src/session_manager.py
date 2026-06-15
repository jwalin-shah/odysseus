import json
import os


class Session:
    def __init__(self, session_id, user):
        self.id = session_id
        self.user = user
        self.messages = []
        self.pending_actions = []
        self.metadata = {}


def make_session(session_id, user):
    return Session(session_id, user)


def append_message(session, role, content):
    session.messages.append({'role': role, 'content': content})


def add_pending_action(session, action_id, action_type, payload):
    session.pending_actions.append({
        'id': action_id,
        'type': action_type,
        'payload': payload
    })


def persist_session(session, base_dir):
    os.makedirs(base_dir, exist_ok=True)
    file_path = os.path.join(base_dir, f"{session.id}.json")

    data = {
        'id': session.id,
        'user': session.user,
        'messages': session.messages,
        'pending_actions': session.pending_actions,
        'metadata': session.metadata,
    }

    with open(file_path, 'w') as f:
        json.dump(data, f)

    return file_path
