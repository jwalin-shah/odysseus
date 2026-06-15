from pathlib import Path


def load_skill(name: str, registry_dir: str | Path) -> str:
    """Read and return the raw text content of a single skill file.

    Args:
        name: The name of the skill. Must be a non-empty string without
            path separators, spaces, or traversal sequences.
        registry_dir: Directory containing the skill files.

    Returns:
        The raw UTF-8 text content of the skill file.

    Raises:
        ValueError: If ``name`` is not a valid skill identifier.
        FileNotFoundError: If the skill file does not exist in ``registry_dir``.
    """
    if not isinstance(name, str) or not name:
        raise ValueError(f"Invalid skill name: {name!r}")

    # Guard against path traversal and obviously unsafe identifiers.
    if any(ch in name for ch in ("/", "\\", "\0", " ")) or ".." in name:
        raise ValueError(f"Invalid skill name: {name!r}")

    registry_path = Path(registry_dir)
    skill_file = registry_path / f"{name}.md"

    if not skill_file.is_file():
        raise FileNotFoundError(
            f"Skill '{name}' not found in '{registry_path}'"
        )

    return skill_file.read_text(encoding="utf-8")
