def _get_defaults() -> dict:
    """Return the hardcoded default configuration dictionary.
    
    This serves as the lowest-priority base layer in the configuration
    loading chain. Values defined here can be overridden by user
    configuration or environment variables.
    """
    return {
        'app_name': 'odysseus',
        'debug': False,
    }
