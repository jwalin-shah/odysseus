from dataclasses import dataclass, field


@dataclass
class TrajectoryStep:
    role: str
    content: str
    tool_calls: list[dict] | None = None
    tool_results: list[dict] | None = None
    metadata: dict | None = None
