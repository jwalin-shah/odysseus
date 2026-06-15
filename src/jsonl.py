import json
import os
import tempfile


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


def _write_jsonl(lines: list, path: str = None) -> str:
    """Write a list of strings to a JSONL file (one per line) and return the path.

    If ``path`` is provided, writes to that path; otherwise creates a temporary
    file with a ``.jsonl`` suffix and returns its path. Useful in tests that
    need a real JSONL file on disk.
    """
    if path is None:
        fd, path = tempfile.mkstemp(suffix=".jsonl")
        os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    return path
