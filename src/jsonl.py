import json


def count_jsonl_valid(path: str) -> int:
    """Return the number of parseable (non-blank, non-corrupt) records in a JSONL file."""
    count = 0
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                json.loads(stripped)
                count += 1
            except (json.JSONDecodeError, ValueError):
                continue
    return count
