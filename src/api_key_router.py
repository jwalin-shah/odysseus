from typing import List
from dataclasses import dataclass, field


@dataclass
class ApiKeyState:
    key: str
    status: str = 'available'
    cooldown_until: float = 0.0


class ApiKeyRouter:
    def __init__(self, keys: List[str], cooldown_seconds: int = 60) -> None:
        self._states: List[ApiKeyState] = [ApiKeyState(key=k) for k in keys]
        self._cursor: int = 0
        self._cooldown_seconds: int = cooldown_seconds
