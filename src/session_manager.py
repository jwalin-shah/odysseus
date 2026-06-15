from datetime import datetime

_sessions: dict[str, list[dict]] = {}


def make_session(session_id: str) -> str:
    if session_id not in _sessions:
        _sessions[session_id] = []
    return session_id


def append_message(session_id: str, role: str, content: str) -> None:
    if session_id not in _sessions:
        raise KeyError(f"Session '{session_id}' does not exist")
    _sessions[session_id].append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    })


def get_history(session_id: str, limit: int | None = None) -> list[dict]:
    if session_id not in _sessions:
        raise KeyError(f"Session '{session_id}' does not exist")
    history = _sessions[session_id]
    if limit is not None:
        return list(history[-limit:])
    return list(history)
