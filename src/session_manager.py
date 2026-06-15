from typing import List, Dict, Any

# In-memory storage for sessions
_sessions: Dict[str, Dict[str, Any]] = {}

def make_session(session_id: str) -> str:
    """Create a new session with the given ID."""
    if session_id not in _sessions:
        _sessions[session_id] = {
            'history': []
        }
    return session_id

def append_message(session_id: str, role: str, content: str) -> None:
    """Append a message to the session's history."""
    if session_id not in _sessions:
        make_session(session_id)
    _sessions[session_id]['history'].append({'role': role, 'content': content})

def get_history(session_id: str) -> List[Dict[str, str]]:
    """Get the conversation history for a session."""
    if session_id not in _sessions:
        return []
    return list(_sessions[session_id]['history'])

def clear_history(session_id: str) -> int:
    """Clear the session's conversation history and return the number of messages removed."""
    if session_id not in _sessions:
        return 0
    count = len(_sessions[session_id]['history'])
    _sessions[session_id]['history'] = []
    return count
