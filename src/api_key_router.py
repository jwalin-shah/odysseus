import time
from typing import Optional


class ApiKeyState:
    def __init__(self, key: str, cooldown_seconds: int = 60) -> None:
        self.key = key
        self.cooldown_seconds = cooldown_seconds
        self.status = "available"
        self.failure_count = 0
        self.cooldown_until: Optional[float] = None

    def mark_exhausted(self) -> None:
        self.status = "exhausted"
        self.failure_count += 1
        self.cooldown_until = time.time() + self.cooldown_seconds

    def reset(self) -> None:
        self.status = "available"
        self.failure_count = 0
        self.cooldown_until = None
