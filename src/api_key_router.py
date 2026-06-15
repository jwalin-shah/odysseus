import time
from typing import Dict, List, Optional


class ApiKeyRouter:
    """Routes requests across a pool of API keys, skipping keys that have
    recently hit a quota/rate-limit error until their cooldown expires.
    """

    DEFAULT_COOLDOWN_SECONDS = 60.0

    def __init__(
        self,
        keys: List[str],
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        self._keys: List[str] = list(keys)
        self._cooldown_seconds: float = float(cooldown_seconds)
        # Maps a known key -> unix timestamp at which the cooldown expires.
        self._exhausted_until: Dict[str, float] = {}

    def report_quota_error(self, key: str) -> None:
        """Record that ``key`` hit a quota/rate-limit error.

        The key will be skipped by subsequent :meth:`get_key` calls until
        the cooldown elapses or :meth:`reset` is called. Unknown keys are
        silently ignored.
        """
        if key not in self._keys:
            return
        self._exhausted_until[key] = time.time() + self._cooldown_seconds

    def is_available(self, key: str) -> bool:
        """Return ``True`` if ``key`` is known and not currently cooling down."""
        if key not in self._keys:
            return False
        exhausted_until = self._exhausted_until.get(key)
        if exhausted_until is None:
            return True
        if time.time() >= exhausted_until:
            # Cooldown elapsed: clear the entry and treat the key as available.
            self._exhausted_until.pop(key, None)
            return True
        return False

    def available_count(self) -> int:
        """Return how many keys are currently available for use."""
        return sum(1 for key in self._keys if self.is_available(key))

    def get_key(self) -> Optional[str]:
        """Return the first available key, or ``None`` if all are exhausted."""
        for key in self._keys:
            if self.is_available(key):
                return key
        return None

    def reset(self) -> None:
        """Clear all cooldown state, making every known key available again."""
        self._exhausted_until.clear()
