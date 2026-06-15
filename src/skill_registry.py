from dataclasses import dataclass


@dataclass
class Skill:
    name: str
    description: str
    body: str


def validate_skill(skill: Skill) -> bool:
    """Return True only if the Skill has non-empty name, description, and body."""
    if not skill.name:
        return False
    if not skill.description:
        return False
    if not skill.body:
        return False
    return True
