import json


def serialize_record(record: dict) -> str:
    return json.dumps(record) + "\n"
