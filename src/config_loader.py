import copy


def _deep_merge(base: dict, overlay: dict) -> dict:
    result = copy.deepcopy(base)
    for key, overlay_value in overlay.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(overlay_value, dict)
        ):
            result[key] = _deep_merge(result[key], overlay_value)
        else:
            result[key] = copy.deepcopy(overlay_value)
    return result
