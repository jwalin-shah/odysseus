import re


def validate_skill_name(name: str) -> bool:
    """Return True if name is a valid skill identifier (lowercase, alnum, dash, underscore; 1-64 chars)."""
    if not isinstance(name, str):
        return False
    pattern = r'^[a-z0-9_-]{1,64}$'
    return bool(re.match(pattern, name))
