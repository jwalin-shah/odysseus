import json
from dataclasses import dataclass, asdict


@dataclass
class TrajectoryStep:
    role: str
    content: str


def build_trajectory_step(role: str, content: str) -> TrajectoryStep:
    return TrajectoryStep(role=role, content=content)


def serialize_trajectory_step(step: TrajectoryStep) -> str:
    return json.dumps(asdict(step))
