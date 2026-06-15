def _build_record(level: str, event: str, ts: str, fields: dict) -> dict:
    """Combine required log keys with additional fields into a single record.

    The resulting dict contains the required ``level``, ``event``, and ``ts``
    keys merged with any extra ``fields``. The required keys come first; any
    keys in ``fields`` that share names with the required keys will overwrite
    them, which is desirable behavior for callers that want to override
    defaults.

    Args:
        level: Log level (e.g. ``"info"``, ``"error"``).
        event: Name of the event being logged.
        ts: Timestamp string (typically ISO 8601).
        fields: Extra structured fields to include in the record.

    Returns:
        A dict ready for JSON serialization.
    """
    record = {"level": level, "event": event, "ts": ts}
    if fields:
        record.update(fields)
    return record
