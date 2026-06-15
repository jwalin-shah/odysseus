import time
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class _KeyState:
    key: str
    status: str = "available"
    failure_count: int = 0
    cooldown_until: Optional[float] = None


class ApiKeyRouter:
    def __init__(self, keys: List[str]) -> None:
        self._states: List[_KeyState] = [_KeyState(key=k) for k in keys]

    def mark_quota_exceeded(self, key: str) -> None:
        for state in self._states:
            if state.key == key:
                state.status = "exhausted"
                state.cooldown_until = time.time()
                state.failure_count += 1
                return
