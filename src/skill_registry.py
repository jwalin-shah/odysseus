import os


def skills_dir_path(base: str | None = None) -> str:
    if base is not None:
        return os.path.join(base, '.odysseus', 'skills')
    return os.path.expanduser('~/.odysseus/skills')
