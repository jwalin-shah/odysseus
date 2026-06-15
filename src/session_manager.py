from datetime import datetime, timezone
from dataclasses import dataclass, field


@dataclass
class Session:
    session_id: str
    owner: str
    created_at: str
    messages: list = field(default_factory=list)
    pending_actions: list = field(default_factory=list)


def make_session(session_id: str, owner: str, created_at: str | None = None) -> Session:
    if created_at is None:
        created_at = datetime.now(timezone.utc).isoformat()
    return Session(
        session_id=session_id,
        owner=owner,
        created_at=created_at,
        messages=[],
        pending_actions=[],
    )
