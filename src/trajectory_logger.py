from dataclasses import dataclass, field, asdict
import json
import time


@dataclass
class Step:
    role: str
    content: str
    metadata: dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Trajectory:
    id: str
    steps: list = field(default_factory=list)


def make_trajectory(traj_id: str) -> Trajectory:
    return Trajectory(id=traj_id)


def record_turn(trajectory: Trajectory, role: str, content: str, metadata: dict = {}) -> Step:
    step = Step(role=role, content=content, metadata=metadata)
    trajectory.steps.append(step)
    return step
