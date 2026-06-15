import copy


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge ``override`` into ``base``.

    Override values win on scalar conflicts and nested dicts are merged
    key-by-key. Returns a new dict without mutating either input.
    """
    result = copy.deepcopy(base)

    for key, override_value in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(override_value, dict)
        ):
            result[key] = deep_merge(result[key], override_value)
        else:
            result[key] = copy.deepcopy(override_value)

    return result
