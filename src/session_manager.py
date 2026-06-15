import time
from src.session import Session


class SessionManager:
    def __init__(self):
        self.sessions = {}
        self.pending_actions = {}
        self._action_id_counter = 0

    def _next_action_id(self) -> str:
        self._action_id_counter += 1
        return str(self._action_id_counter)

    def add_pending_action(self, session_id: str, task: str, params: dict) -> str:
        if session_id not in self.sessions:
            self.sessions[session_id] = Session(session_id)

        action_id = self._next_action_id()
        if session_id not in self.pending_actions:
            self.pending_actions[session_id] = {}

        self.pending_actions[session_id][action_id] = {
            "task": task,
            "params": params,
            "result": None,
            "completed": False,
            "created_at": time.time(),
        }
        return action_id

    def resolve_pending_action(self, session_id: str, action_id: str, result: object) -> bool:
        if session_id not in self.pending_actions:
            return False
        if action_id not in self.pending_actions[session_id]:
            return False

        action = self.pending_actions[session_id][action_id]
        action["result"] = result
        action["completed"] = True
        return True
