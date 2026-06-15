from src.session import Session


class SessionManager:
    def __init__(self):
        self.sessions = {}

    def get_or_create_session(self, session_id: str) -> Session:
        if session_id not in self.sessions:
            self.sessions[session_id] = Session(session_id)
        return self.sessions[session_id]

    def list_sessions(self) -> list:
        return list(self.sessions.keys())
