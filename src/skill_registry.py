from dataclasses import dataclass, asdict
from pathlib import Path

import yaml


@dataclass
class Skill:
    name: str
    description: str
    body: str = ""


def save_skill_file(skill: Skill, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {k: v for k, v in asdict(skill).items() if k != 'body'}
    frontmatter = yaml.safe_dump(metadata, default_flow_style=False, sort_keys=False)
    content = f"---\n{frontmatter}---\n\n{skill.body}"
    path.write_text(content)


def load_skill_file(path: Path) -> Skill:
    text = path.read_text()
    parts = text.split("---", 2)
    if len(parts) >= 3:
        metadata = yaml.safe_load(parts[1]) or {}
        body = parts[2].lstrip("\n")
    else:
        metadata = {}
        body = text
    return Skill(
        name=metadata.get("name", ""),
        description=metadata.get("description", ""),
        body=body,
    )
