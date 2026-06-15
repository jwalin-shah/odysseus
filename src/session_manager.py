from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Session:
    session_id: str
    owner: str
    messages: list = field(default_factory=list)


def make_session(session_id: str, owner: str) -> Session:
    return Session(session_id=session_id, owner=owner)


def append_message(session: Session, role: str, content: str) -> None:
    session.messages.append({"role": role, "content": content})


def get_conversation_history(session: Session, limit: int | None = None) -> list:
    history = list(session.messages)
    if limit is not None:
        return history[-limit:]
    return history
