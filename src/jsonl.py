import json
from typing import Iterator, Any, Optional


def read_jsonl(path: str) -> Iterator[Any]:
    """Generator that opens a JSONL file and yields each successfully parsed record,
    silently skipping blank lines and lines that fail to parse.
    """
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                continue
