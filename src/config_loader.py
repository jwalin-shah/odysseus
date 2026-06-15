import copy


def deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, override_value in override.items():
        if key in result:
            base_value = result[key]
            if isinstance(base_value, dict) and isinstance(override_value, dict):
                result[key] = deep_merge(base_value, override_value)
            else:
                result[key] = copy.deepcopy(override_value)
        else:
            result[key] = copy.deepcopy(override_value)
    return result


def load_defaults() -> dict:
    """Return the built-in baseline configuration dictionary.

    This is the lowest-priority configuration layer: user settings,
    environment variables, and explicit overrides are merged on top
    of it via deep_merge(). Values here are deliberately conservative
    so that running the app out of the box (without any user config)
    produces a working, safe default.
    """
    return {
        "host": "localhost",
        "port": 8000,
        "debug": False,
        "database": {
            "host": "localhost",
            "port": 5432,
            "name": "app",
            "pool": 5,
        },
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        },
        "cache": {
            "enabled": True,
            "ttl": 300,
        },
    }


assert load_defaults()['host'] == 'localhost'
assert load_defaults()['database']['pool'] == 5
assert isinstance(load_defaults(), dict)
