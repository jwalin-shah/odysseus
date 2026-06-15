from dataclasses import dataclass, field
import time
import uuid


@dataclass
class Session:
    session_id: str
    messages: list = field(default_factory=list)
    pending_actions: list = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict = field(default_factory=dict)


def make_session(session_id: str) -> 'Session':
    return Session(session_id=session_id)
