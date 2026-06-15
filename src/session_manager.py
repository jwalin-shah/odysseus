# src/session_manager.py
"""Session manager module providing functions to track sessions and pending actions."""

_sessions = {}

def make_session(session_id: str) -> str:
    """Create a new session if it does not already exist.
    
    Args:
        session_id: The unique identifier for the session.
    
    Returns:
        The session id.
    """
    if session_id not in _sessions:
        _sessions[session_id] = {'pending': set()}
    return session_id

def add_pending_action(session_id: str, action: dict) -> None:
    """Add a pending action to the specified session.
    
    Args:
        session_id: The session identifier.
        action: A dictionary representing the action. Must contain an 'id' key.
    """
    if session_id not in _sessions:
        make_session(session_id)
    action_id = action.get('id')
    if action_id is not None:
        _sessions[session_id]['pending'].add(action_id)

def resolve_pending_action(session_id: str, action_id: str) -> None:
    """Mark a pending action as resolved by removing it from the pending set.
    
    Args:
        session_id: The session identifier.
        action_id: The identifier of the action to resolve.
    """
    if session_id in _sessions:
        _sessions[session_id]['pending'].discard(action_id)

def pending_action_count(session_id: str) -> int:
    """Return the number of pending (unresolved) actions for the given session.
    
    Args:
        session_id: The session identifier.
    
    Returns:
        The integer count of pending actions. Returns 0 if the session does not exist.
    """
    if session_id not in _sessions:
        return 0
    return len(_sessions[session_id]['pending'])
