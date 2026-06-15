class SessionManager:
    def __init__(self, storage_dir: str = '/tmp/odysseus_sessions') -> None:
        self.storage_dir = storage_dir
        self._sessions = {}
