class ApiKeyManager:
    def __init__(self):
        self._keys = {}

    def add_key(self, key_id: str, key_value: str) -> None:
        """Register a new API key under the given key_id for later round-robin selection."""
        if not key_id:
            raise ValueError("key_id cannot be empty")
        if key_id in self._keys:
            raise ValueError(f"Key '{key_id}' already exists")
        self._keys[key_id] = key_value

    def active_keys(self):
        """Return the list of currently active (registered) key IDs."""
        return list(self._keys.keys())
