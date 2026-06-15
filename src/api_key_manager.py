from typing import Optional, Set, Dict, Any


class APIKeyManager:
    """Manages a set of API keys and their quota exhaustion state."""

    def __init__(self) -> None:
        self._keys: Dict[str, Dict[str, Any]] = {}

    def add_key(self, key_id: str, key_data: Optional[Dict[str, Any]] = None) -> None:
        """Register a new API key with the manager."""
        if key_data is None:
            key_data = {}
        if "quota_exhausted" not in key_data:
            key_data["quota_exhausted"] = False
        self._keys[key_id] = key_data

    def remove_key(self, key_id: str) -> None:
        """Unregister an API key."""
        if key_id not in self._keys:
            raise KeyError(f"Key '{key_id}' is not registered")
        del self._keys[key_id]

    def active_keys(self) -> Set[str]:
        """Return the set of key IDs that are not currently quota-exhausted."""
        return {
            key_id
            for key_id, data in self._keys.items()
            if not data.get("quota_exhausted", False)
        }

    def is_quota_exhausted(self, key_id: str) -> bool:
        """Return whether the given key is flagged as quota-exhausted."""
        if key_id not in self._keys:
            raise KeyError(f"Key '{key_id}' is not registered")
        return bool(self._keys[key_id].get("quota_exhausted", False))

    def mark_quota_error(self, key_id: str) -> None:
        """Flag a key as quota-exhausted so the router skips it on selection.

        Args:
            key_id: The identifier of the key to mark as quota-exhausted.

        Raises:
            KeyError: If the key_id is not registered with the manager.
        """
        if key_id not in self._keys:
            raise KeyError(f"Key '{key_id}' is not registered")
        self._keys[key_id]["quota_exhausted"] = True
        return None
