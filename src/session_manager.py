from __future__ import annotations
from typing import Any


class Session:
    """Represents a user session with a list of pending actions."""
    
    def __init__(self, session_id: str, user: str) -> None:
        self.session_id = session_id
        self.user = user
        self.pending_actions: list[dict] = []


def make_session(session_id: str, user: str) -> Session:
    """Create and return a new Session with the given id and user."""
    return Session(session_id, user)


def add_pending_action(
    session: Session,
    action_id: str,
    action_type: str,
    params: dict,
) -> None:
    """Append a new pending action to the session."""
    session.pending_actions.append(
        {
            "id": action_id,
            "type": action_type,
            "params": params,
            "status": "pending",
        }
    )


def list_pending_actions(session: Session) -> list[dict]:
    """Return only the actions whose status is still 'pending'."""
    return [
        action
        for action in session.pending_actions
        if action.get("status") == "pending"
    ]
