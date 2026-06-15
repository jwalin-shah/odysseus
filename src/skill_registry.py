from typing import List


class Skill:
    def __init__(self, name: str, triggers: List[str] = None, description: str = ""):
        self.name = name
        self.triggers = triggers if triggers is not None else []
        self.description = description


def match_skill_by_query(query: str, skills: List[Skill]) -> List[Skill]:
    query_lower = query.lower()
    results = []
    for skill in skills:
        if query_lower in skill.name.lower():
            results.append(skill)
            continue
        if any(query_lower in trigger.lower() for trigger in skill.triggers):
            results.append(skill)
            continue
        if query_lower in skill.description.lower():
            results.append(skill)
            continue
    return results
