import json
import os

def save_seen_hashes(path: str, hashes: set) -> None:
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(sorted(list(hashes)), f)
