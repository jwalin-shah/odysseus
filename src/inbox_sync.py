import json
import os


def load_seen_hashes(path: str = 'data/inbox_seen.json') -> set:
    """Load the set of previously seen message hashes from a JSON file.

    Returns an empty set if the file is missing or contains invalid JSON.
    """
    if not os.path.exists(path):
        return set()
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError):
        return set()
    if not isinstance(data, (list, set, tuple)):
        return set()
    return set(data)
