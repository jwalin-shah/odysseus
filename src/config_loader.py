import copy
import json
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


def _default_config() -> dict:
    """Return the built-in default configuration dictionary."""
    return {
        "server": {
            "host": "127.0.0.1",
            "port": 8000,
        },
        "llm": {
            "timeout": 60,
            "model": "default",
        },
    }


def _load_file_config(path: str) -> dict:
    """Load a JSON config file; return an empty dict on any failure.

    Missing files, unreadable files, and invalid JSON all degrade
    gracefully to an empty dictionary so callers can still merge
    defaults and environment overrides on top.
    """
    if not path:
        return {}
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _apply_env_overrides(config: dict, prefix: str) -> dict:
    """Overlay OS environment variables onto ``config``.

    Variables starting with ``prefix`` have the prefix stripped and
    the remainder split on ``__`` to form a nested key path (e.g.
    ``ODYSSEUS_SERVER__PORT=9999`` sets ``config["server"]["port"]``).
    Values are coerced via :func:`_coerce_env_value` before being
    assigned. The original ``config`` is not mutated.
    """
    result = copy.deepcopy(config)
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        remainder = env_key[len(prefix):]
        if not remainder:
            continue
        key_path = remainder.lower().split("__")
        coerced = _coerce_env_value(env_value)
        current = result
        for key in key_path[:-1]:
            existing = current.get(key)
            if not isinstance(existing, dict):
                existing = {}
                current[key] = existing
            current = existing
        current[key_path[-1]] = coerced
    return result


def load_config(path: str, env_prefix: str = "ODYSSEUS_") -> dict:
    """Merge defaults, file config, and env overrides and return the result.

    Precedence (lowest to highest): built-in defaults, JSON file at
    ``path``, OS environment variables prefixed by ``env_prefix``.
    """
    config = _default_config()
    file_config = _load_file_config(path)
    config = deep_merge(config, file_config)
    config = _apply_env_overrides(config, env_prefix)
    return config


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
    # Smoke test for load_config with a missing file path.
    _smoke = load_config("/nonexistent/path/missing.json")
    assert _smoke["server"]["host"] == "127.0.0.1"
    assert _smoke["server"]["port"] == 8000
