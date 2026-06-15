from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Session:
    session_id: str
    user_id: str
    pending_actions: List[Dict[str, Any]] = field(default_factory=list)


def make_session(session_id: str, user_id: str) -> Session:
    return Session(session_id=session_id, user_id=user_id)


def add_pending_action(session: Session, action_id: str, action_type: str, payload: dict) -> None:
    session.pending_actions.append({
        'action_id': action_id,
        'action_type': action_type,
        'payload': payload,
        'status': 'pending'
    })
