import json


def _safe_parse_json_line(line: str):
    """Attempt to parse a single line as JSON.

    Returns the parsed Python object on success, or None on any
    ValueError (e.g. blank input, malformed JSON, or non-JSON text).
    """
    try:
        return json.loads(line)
    except ValueError:
        return None
