from datetime import datetime
from typing import List, Dict, Any


class Session:
    def __init__(self, session_id: str, user: str):
        self.session_id = session_id
        self.user = user
        self.messages: List[Dict[str, Any]] = []


def make_session(session_id: str, user: str) -> Session:
    return Session(session_id, user)


def append_message(session: Session, role: str, content: str) -> None:
    """Append a message to the session's conversation history."""
    message = {
        'role': role,
        'content': content,
        'timestamp': datetime.now().isoformat()
    }
    session.messages.append(message)
