from dataclasses import dataclass, field, asdict
import json
import os
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


def make_trajectory(session_id: str = '', traj_id: str = '', steps: list = None) -> Trajectory:
    """Create a Trajectory. Accepts ``session_id`` (preferred) or ``traj_id``
    for backwards compatibility, plus an optional ``steps`` list."""
    tid = session_id or traj_id
    return Trajectory(id=tid, steps=list(steps) if steps else [])


def record_turn(trajectory: Trajectory, role: str, content: str, metadata: dict = {}) -> Step:
    step = Step(role=role, content=content, metadata=metadata)
    trajectory.steps.append(step)
    return step


def save_trajectory(path: str, traj: Trajectory) -> None:
    """Append a Trajectory as a single JSONL line to the file at path,
    creating parent directories as needed."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, 'a') as f:
        f.write(json.dumps(asdict(traj)) + '\n')


if __name__ == '__main__':
    import tempfile
    _p = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False).name
    save_trajectory(_p, make_trajectory(session_id='s', steps=[Step(role='user', content='x')]))
    assert open(_p).read().endswith(chr(10))
    _p = tempfile.NamedTemporaryFile(suffix='.jsonl', delete=False).name
    save_trajectory(_p, make_trajectory(session_id='s1', steps=[Step(role='user', content='x')]))
    save_trajectory(_p, make_trajectory(session_id='s2', steps=[Step(role='user', content='y')]))
    assert open(_p).read().count(chr(10)) == 2
