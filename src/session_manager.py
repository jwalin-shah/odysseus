from datetime import datetime, timezone

# In-memory session storage
_sessions = {}


def make_session(session_id: str) -> dict:
    """Create a new session with the given ID and return it."""
    session = {
        'id': session_id,
        'messages': []
    }
    _sessions[session_id] = session
    return session


def get_session(session_id: str) -> dict:
    """Retrieve a session by ID. Raises KeyError if not found."""
    if session_id not in _sessions:
        raise KeyError(f"Session '{session_id}' not found")
    return _sessions[session_id]


def append_message(session_id: str, role: str, content: str) -> None:
    """Append a new message to the session's conversation history.

    The message is stamped with the current UTC time.
    Raises KeyError if the session does not exist.
    """
    session = get_session(session_id)
    message = {
        'role': role,
        'content': content,
        'timestamp': datetime.now(timezone.utc),
    }
    session['messages'].append(message)
