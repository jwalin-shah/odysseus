from typing import List


class Skill:
    def __init__(self, name: str, tags: List[str] = None):
        self.name = name
        self.tags = tags if tags is not None else []


def match_skills_by_tags(required_tags: List[str], skills: List[Skill]) -> List[Skill]:
    if not required_tags:
        return list(skills)
    required_set = {tag.lower() for tag in required_tags}
    result = []
    for skill in skills:
        skill_tags = {tag.lower() for tag in skill.tags}
        if required_set.issubset(skill_tags):
            result.append(skill)
    return result
