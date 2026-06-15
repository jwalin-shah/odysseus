from src.session import Session


class SessionManager:
    def __init__(self):
        self._sessions = {}

    def get_or_create_session(self, session_id: str) -> Session:
        if session_id not in self._sessions:
            self._sessions[session_id] = Session(session_id)
        return self._sessions[session_id]
