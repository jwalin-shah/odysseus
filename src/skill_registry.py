from pathlib import Path


def _resolve_skills_dir() -> Path:
    skills_dir = Path.home() / ".odysseus" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir
