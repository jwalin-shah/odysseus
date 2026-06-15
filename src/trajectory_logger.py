from datetime import datetime, timezone


def make_trajectory_record(session_id: str, messages: list[dict], model: str, metadata: dict | None = None) -> dict:
    return {
        'session_id': session_id,
        'model': model,
        'messages': messages,
        'metadata': metadata,
        'created_at': datetime.now(timezone.utc).isoformat(),
    }
