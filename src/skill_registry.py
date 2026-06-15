from pathlib import Path
import os


def skills_dir() -> Path:
    """Resolve and return the skills directory.

    Default location: ~/.odysseus/skills/
    Override: set the ODYSSEUS_SKILLS_DIR environment variable.
    """
    override = os.environ.get("ODYSSEUS_SKILLS_DIR")
    if override:
        return Path(override)
    return Path.home() / ".odysseus" / "skills"
