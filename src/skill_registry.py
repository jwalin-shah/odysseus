import re

# Pattern: only lowercase letters, digits, hyphens, and underscores
_SAFE_SKILL_NAME_PATTERN = re.compile(r'^[a-z0-9_-]+$')


def validate_skill_name(name: str) -> bool:
    """Validate a skill name allows only safe slug characters.

    Allowed characters: lowercase letters (a-z), digits (0-9),
    hyphens (-), and underscores (_). The name must be non-empty.

    Args:
        name: The candidate skill name to validate.

    Returns:
        True if the name consists solely of allowed characters and
        is non-empty; False otherwise.
    """
    if not isinstance(name, str) or not name:
        return False
    return bool(_SAFE_SKILL_NAME_PATTERN.fullmatch(name))
