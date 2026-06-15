import json
import yaml
from pathlib import Path


def _load_from_file(path: str) -> dict:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")
    
    suffix = file_path.suffix.lower()
    with open(file_path, 'r') as f:
        if suffix == '.json':
            return json.load(f)
        elif suffix in ('.yaml', '.yml'):
            return yaml.safe_load(f)
        else:
            raise ValueError(f"Unsupported file format: {path}")
