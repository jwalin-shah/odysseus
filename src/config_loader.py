"""Configuration loader module providing built-in default configuration."""

from typing import Dict


def load_defaults() -> dict:
    """Return the built-in default configuration dictionary.

    Provides sensible baseline values for all known configuration keys.
    """
    defaults: Dict[str, object] = {
        "app_name": "odysseus",
        "debug": False,
        "version": "1.0.0",
        "log_level": "INFO",
        "max_connections": 100,
        "timeout_seconds": 30,
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "odysseus_db",
        },
    }
    return defaults
