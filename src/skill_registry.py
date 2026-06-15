from pathlib import Path


def _resolve_skills_dir() -> Path:
    skills_dir = Path.home() / ".odysseus" / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)
    return skills_dir


def get_skills_dir() -> str:
    return str(_resolve_skills_dir())


def validate_skill_data(skill: dict) -> tuple:
    """Validate a skill dict has required 'name' field with non-empty string value.

    Returns:
        tuple: (is_valid: bool, error_message: str)
    """
    if not isinstance(skill, dict):
        return (False, "skill must be a dict")

    if 'name' not in skill:
        return (False, "missing required 'name' field")

    name = skill['name']
    if not isinstance(name, str):
        return (False, "'name' must be a string")

    if not name.strip():
        return (False, "'name' must be a non-empty string")

    return (True, "")
