import os
from pathlib import Path

def skills_dir() -> str:
    """Resolve the absolute path to the skills directory (~/.odysseus/skills/),
    honoring an ODYSSEUS_SKILLS_DIR env override and creating the directory if missing.
    """
    override = os.environ.get('ODYSSEUS_SKILLS_DIR')
    if override:
        path = Path(override)
    else:
        path = Path.home() / '.odysseus' / 'skills'
    
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
