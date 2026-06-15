import datetime


def now_iso() -> str:
    """Return the current UTC timestamp as an ISO 8601 string with timezone info."""
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
