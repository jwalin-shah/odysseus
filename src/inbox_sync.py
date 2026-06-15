import json
import os

def load_seen_hashes(path: str) -> set:
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r") as f:
            data = json.load(f)
        return set(data) if data else set()
    except (json.JSONDecodeError, ValueError):
        return set()
