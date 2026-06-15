from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class Trajectory:
    id: str
    session_id: str
    created_at: str
    messages: list[dict]
    metadata: dict
