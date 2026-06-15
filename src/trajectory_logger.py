from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Trajectory:
    trajectory_id: str
    steps: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

def make_trajectory(trajectory_id: str, metadata: dict | None = None) -> Trajectory:
    if metadata is None:
        metadata = {}
    return Trajectory(trajectory_id=trajectory_id, steps=[], metadata=metadata)
