"""Structured logger module.

Provides a function returning the required keys for every emitted log record.
"""

_REQUIRED_KEYS = ('level', 'event', 'timestamp')


def required_keys() -> tuple:
    """Return the tuple of keys that every emitted log record must contain.

    Returns:
        tuple: The required log record keys: 'level', 'event', 'timestamp'.
    """
    return _REQUIRED_KEYS
