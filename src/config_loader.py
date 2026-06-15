def load_defaults() -> dict:
    """Return the hardcoded baseline configuration (lowest-priority layer).

    This dict is overridden by file-based config and environment variables.
    """
    return {
        'debug': False,
        'db': {
            'host': 'localhost',
            'port': 5432,
        },
    }
