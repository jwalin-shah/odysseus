import copy
import os


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


def _coerce_env_value(value: str) -> object:
    """Coerce a raw env-var string into bool, int, float, or str.

    Bool check is case-insensitive and only matches the literal strings
    'true' / 'false' — '1' / '0' are not treated as booleans and stay ints.
    Falls back to the original string when no numeric conversion applies.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if not isinstance(value, str):
        return value
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in ("null", "none"):
        return None
    stripped = value.strip()
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass
    return value


def _apply_env_overrides(config: dict, prefix: str) -> dict:
    """Apply environment variable overrides to a config dict.

    Scans ``os.environ`` for variables beginning with ``prefix``. The
    suffix after the prefix is interpreted as ``SECTION__KEY`` (split
    on a double underscore) and the value is coerced via
    :func:`_coerce_env_value`. The collected overrides are then
    deep-merged into ``config`` using :func:`deep_merge` and the
    merged result is returned.
    """
    overrides: dict = {}
    for env_name, env_value in os.environ.items():
        if not env_name.startswith(prefix):
            continue
        remainder = env_name[len(prefix):]
        parts = remainder.split("__")
        if len(parts) != 2:
            # Only the two-level SECTION__KEY form is supported.
            continue
        section, key = parts[0].lower(), parts[1].lower()
        overrides.setdefault(section, {})[key] = _coerce_env_value(env_value)
    return deep_merge(config, overrides)


def test_deep_merge_non_dict_replace() -> None:
    """Asserts that when b holds a non-dict (scalar/list/None) at a key where
    a has a dict, the non-dict value fully replaces the dict."""
    assert deep_merge({'a': {'x': 1}}, {'a': 7}) == {'a': 7}
    assert deep_merge({'a': [1, 2]}, {'a': 'scalar'}) == {'a': 'scalar'}
    assert deep_merge({'a': 5}, {'a': None}) == {'a': None}


if __name__ == "__main__":
    assert _coerce_env_value('true') is True
    assert _coerce_env_value('42') == 42
    assert _coerce_env_value('hello') == 'hello'
    test_deep_merge_non_dict_replace()
