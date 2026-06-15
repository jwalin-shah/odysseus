from typing import List, Dict, Any

_sessions: Dict[str, List[Dict[str, Any]]] = {}


def make_session(session_id: str) -> str:
    _sessions[session_id] = []
    return session_id


def append_message(session_id: str, role: str, content: str) -> None:
    if session_id not in _sessions:
        _sessions[session_id] = []
    _sessions[session_id].append({"role": role, "content": content})


def get_history(session_id: str) -> List[Dict[str, Any]]:
    return _sessions.get(session_id, [])


def trim_history(session_id: str, keep_last: int) -> int:
    history = get_history(session_id)
    current_len = len(history)
    if current_len <= keep_last:
        return 0
    to_remove = current_len - keep_last
    if keep_last > 0:
        _sessions[session_id] = history[-keep_last:]
    else:
        _sessions[session_id] = []
    return to_remove
