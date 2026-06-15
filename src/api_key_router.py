class ApiKeyRouter:
    def __init__(self, keys: list[str], cooldown_seconds: float = 60.0) -> None:
        if not keys:
            raise ValueError("keys must be a non-empty list")
        self.cooldown_seconds = cooldown_seconds
        self._states = [{"key": k, "available_at": 0.0} for k in keys]
        self._cursor = 0
