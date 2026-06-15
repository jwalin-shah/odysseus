from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    name: str
    description: str = ""
    tags: tuple[str, ...] = ()
    body: str = ""
    path: Path | None = None
