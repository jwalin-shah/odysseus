from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class Step:
    role: str
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Trajectory:
    id: str
    steps: List[Step] = field(default_factory=list)


def make_trajectory(traj_id: str) -> Trajectory:
    return Trajectory(id=traj_id)


def record_turn(
    traj: Trajectory,
    role: str,
    content: str,
    tool_calls: list[dict] | None = None,
    tool_call_id: str | None = None,
    name: str | None = None,
) -> Trajectory:
    step = Step(
        role=role,
        content=content,
        tool_calls=tool_calls,
        tool_call_id=tool_call_id,
        name=name,
    )
    traj.steps.append(step)
    return traj
