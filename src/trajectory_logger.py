from dataclasses import dataclass, field, asdict
import json
import os
from datetime import datetime, timezone


@dataclass
class Step:
    role: str
    content: str
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tool_calls: list = field(default_factory=list)
    tool_results: list = field(default_factory=list)


@dataclass
class Trajectory:
    id: str
    steps: list = field(default_factory=list)


def make_trajectory(session_id: str = '', traj_id: str = '', steps: list = None) -> Trajectory:
    """Create a Trajectory. Accepts ``session_id`` (preferred) or ``traj_id``
    for backwards compatibility, plus an optional ``steps`` list."""
    tid = session_id or traj_id
    return Trajectory(id=tid, steps=list(steps) if steps else [])


def build_step(role: str, content: str, tool_calls: list | None = None, tool_results: list | None = None, metadata: dict | None = None) -> Step:
    """Construct a Step from raw turn data, stamping it with the current UTC ISO timestamp
    and defaulting optional fields to empty values."""
    return Step(
        role=role,
        content=content,
        tool_calls=tool_calls if tool_calls is not None else [],
        tool_results=tool_results if tool_results is not None else [],
        metadata=metadata if metadata is not None else {},
    )


def record_turn(trajectory: Trajectory, role: str, content: str, metadata: dict = {}) -> Step:
    step = Step(role=role, content=content, metadata=metadata)
    trajectory.steps.append(step)
    return step


def list_trajectory_files(directory: str) -> list:
    """Return a sorted list of ``*.jsonl`` trajectory file paths in ``directory``,
    ignoring non-jsonl files and subdirectories."""
    files = []
    for entry in os.listdir(directory):
        full_path = os.path.join(directory, entry)
        if os.path.isfile(full_path) and entry.endswith('.jsonl'):
            files.append(full_path)
    return sorted(files)


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
