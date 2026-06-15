from dataclasses import dataclass, field
from typing import List


@dataclass
class Skill:
    name: str
    description: str = ""
    triggers: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    body: str = ""
