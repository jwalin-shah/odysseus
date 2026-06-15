import json
import os
from src.app_helpers import read_if_exists


def load_sync_state(path: str) -> set:
    content = read_if_exists(path)
    if not content:
        return set()
    return set(json.loads(content))
