def parse_api_keys_config(raw: dict) -> list[dict]:
    """
    Parses a config dict into a normalized list of API key records.

    Each record contains: id, key, provider, and weight.
    Missing optional fields are filled with sensible defaults.
    """
    if not isinstance(raw, dict):
        return []

    keys = raw.get("keys", [])
    if not isinstance(keys, list):
        return []

    result = []
    for entry in keys:
        if not isinstance(entry, dict):
            continue
        record = {
            "id": entry.get("id"),
            "key": entry.get("key"),
            "provider": entry.get("provider", ""),
            "weight": entry.get("weight", 1),
        }
        result.append(record)
    return result
