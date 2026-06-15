import os


def ensure_skills_dir(base: str | None = None) -> str:
    if base is None:
        base = os.getcwd()
    skills_dir = os.path.join(base, 'skills')
    os.makedirs(skills_dir, exist_ok=True)
    return os.path.abspath(skills_dir)
