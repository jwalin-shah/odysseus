import time
from typing import List, Optional


class ApiKeyRouter:
    """Routes requests across an ordered list of API keys, honoring cooldown periods
    after quota errors."""

    def __init__(self, keys: list[str], cooldown_seconds: float = 60.0) -> None:
        """Initialize the router with an ordered list of API keys and a default
        cooldown duration applied after a quota error."""
        self.keys: list[str] = list(keys)
        self.cooldown_seconds: float = float(cooldown_seconds)
        # Map of key -> unix timestamp at which the cooldown expires.
        self._cooldowns: dict[str, float] = {}
        # Pointer used to rotate through keys in order for load distribution.
        self._cursor: int = 0

    def get_key(self) -> Optional[str]:
        """Return the next available key that is not in cooldown, or None if all
        keys are currently cooling down."""
        now = time.time()
        # Purge expired cooldowns lazily.
        expired = [k for k, until in self._cooldowns.items() if until <= now]
        for k in expired:
            del self._cooldowns[k]

        n = len(self.keys)
        for offset in range(n):
            idx = (self._cursor + offset) % n
            candidate = self.keys[idx]
            if candidate not in self._cooldowns:
                self._cursor = (idx + 1) % n
                return candidate
        return None

    def mark_quota_error(self, key: str, cooldown_seconds: Optional[float] = None) -> None:
        """Place ``key`` into cooldown after a quota error. By default the
        router-wide ``cooldown_seconds`` is used; an override may be supplied."""
        duration = self.cooldown_seconds if cooldown_seconds is None else float(cooldown_seconds)
        self._cooldowns[key] = time.time() + duration

    def release(self, key: str) -> None:
        """Manually clear a key's cooldown."""
        self._cooldowns.pop(key, None)

    def is_in_cooldown(self, key: str) -> bool:
        """Return True if ``key`` is currently cooling down."""
        until = self._cooldowns.get(key)
        if until is None:
            return False
        if until <= time.time():
            self._cooldowns.pop(key, None)
            return False
        return True

    def cooldown_remaining(self, key: str) -> float:
        """Return seconds remaining on ``key``'s cooldown, or 0.0 if none."""
        until = self._cooldowns.get(key)
        if until is None:
            return 0.0
        remaining = until - time.time()
        if remaining <= 0:
            self._cooldowns.pop(key, None)
            return 0.0
        return remaining

    def __repr__(self) -> str:
        return (
            f"ApiKeyRouter(keys={self.keys!r}, "
            f"cooldown_seconds={self.cooldown_seconds!r})"
        )
