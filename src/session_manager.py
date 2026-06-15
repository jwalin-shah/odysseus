from typing import Any


# Global in-memory store for sessions
_sessions: dict[str, dict[str, Any]] = {}


def make_session(session_id: str) -> dict:
    """Create a new session if it doesn't exist, then return it."""
    if session_id not in _sessions:
        _sessions[session_id] = {
            "id": session_id,
            "pending_actions": [],
        }
    return _sessions[session_id]


def add_pending_action(session_id: str, action: dict) -> None:
    """Append a pending action to the session's pending actions list."""
    if session_id not in _sessions:
        make_session(session_id)
    _sessions[session_id]["pending_actions"].append(action)


def resolve_pending_action(session_id: str, action_id: str) -> None:
    """Remove a pending action from the session by its 'id' field."""
    if session_id not in _sessions:
        return
    session = _sessions[session_id]
    session["pending_actions"] = [
        action for action in session["pending_actions"]
        if action.get("id") != action_id
    ]


def list_pending_actions(session_id: str) -> list[dict]:
    """Return the list of all currently unresolved pending actions attached to the session, preserving insertion order."""
    if session_id not in _sessions:
        return []
    return list(_sessions[session_id]["pending_actions"])
