import json


def read_jsonl(path: str):
    """Yield valid JSON records from a JSONL file, skipping empty/invalid lines."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def read_jsonl_list(path: str) -> list:
    """Materialize read_jsonl into a plain list of all valid records in the file."""
    return list(read_jsonl(path))
