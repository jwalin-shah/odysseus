from pathlib import Path


def get_skills_dir() -> Path:
    skills_dir = Path.home() / ".odysseus" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir
