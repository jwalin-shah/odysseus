import json


def serialize_trajectory_jsonl(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, separators=(",", ":"))
