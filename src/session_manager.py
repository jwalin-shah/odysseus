import uuid
import time


class Session:
    def __init__(self, name: str):
        self.name = name
        self.pending_actions = []


def make_session(name: str) -> 'Session':
    return Session(name)


def queue_pending_action(session: 'Session', action: str, args: dict = None) -> str:
    action_id = str(uuid.uuid4())
    pending_action = {
        'id': action_id,
        'action': action,
        'args': args if args is not None else {},
        'queued_at': time.time(),
    }
    session.pending_actions.append(pending_action)
    return action_id
