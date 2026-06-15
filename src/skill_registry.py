from dataclasses import dataclass


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    tags: list[str]
    body: str
    path: str
