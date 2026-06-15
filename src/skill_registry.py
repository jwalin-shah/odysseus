from pathlib import Path


def list_skills(registry_dir: str | Path) -> list[str]:
    """Enumerate the available skill names in the registry directory, sorted alphabetically."""
    registry_path = Path(registry_dir)
    if not registry_path.exists() or not registry_path.is_dir():
        return []
    return sorted(p.name for p in registry_path.iterdir() if p.is_dir())
