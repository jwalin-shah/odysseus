class Session:
    def __init__(self, name):
        self.name = name
        self.messages = []


def make_session(name):
    return Session(name)


def append_message(session, role, content):
    session.messages.append({'role': role, 'content': content})


def get_conversation_history(session, limit=None):
    if limit is None:
        return list(session.messages)
    return list(session.messages[-limit:])
