from dataclasses import dataclass, field
import time


@dataclass
class Session:
    session_id: str
    owner: str
    messages = field(default_factory=list)
    pending_actions = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


def make_session(session_id: str, owner: str) -> Session:
    """Create a new Session with the given id and owner, initialized with empty conversation history and pending actions."""
    return Session(session_id=session_id, owner=owner)
