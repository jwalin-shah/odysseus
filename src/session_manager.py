from typing import List, Dict, Any

class Session:
    def __init__(self, session_id: str, owner: str):
        self.session_id = session_id
        self.owner = owner
        self.pending_actions: List[Dict[str, Any]] = []

def make_session(session_id: str, owner: str) -> Session:
    """Create a new session with the given id and owner."""
    return Session(session_id, owner)

def add_pending_action(session: Session, action_id: str, action_data: dict) -> None:
    """Add a pending action to the session."""
    session.pending_actions.append({
        'action_id': action_id,
        'status': 'pending',
        'data': action_data,
        'result': None
    })

def resolve_pending_action(session: Session, action_id: str, status: str, result: dict | None = None) -> dict:
    """
    Mark the pending action with the given action_id as resolved.
    
    Args:
        session: The session containing the pending action.
        action_id: The id of the action to resolve.
        status: The new status, must be one of {'completed', 'cancelled', 'failed'}.
        result: Optional result data to associate with the action.
    
    Returns:
        The updated action entry as a dict, or an empty dict if the action was not found.
    """
    valid_statuses = {'completed', 'cancelled', 'failed'}
    if status not in valid_statuses:
        raise ValueError(f"Invalid status: {status}. Must be one of {valid_statuses}")
    
    for action in session.pending_actions:
        if action['action_id'] == action_id:
            action['status'] = status
            if result is not None:
                action['result'] = result
            return action
    
    return {}
