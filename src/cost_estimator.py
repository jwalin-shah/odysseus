def parse_trajectory_step(step: dict) -> tuple[str, int, int]:
    """Extract (model_id, input_tokens, output_tokens) from a trajectory step.

    Tolerates common key aliases and a nested 'usage' dict (e.g. as produced
    by OpenAI-style APIs).
    """
    # Model ID aliases
    model_id = ""
    for key in ("model_id", "model", "id", "name"):
        if key in step:
            model_id = step[key]
            break

    # Input token aliases at top level
    input_tokens = None
    for key in ("input_tokens", "prompt_tokens", "tokens_in", "input"):
        if key in step:
            input_tokens = step[key]
            break

    # Fallback: look inside a nested 'usage' dict
    if input_tokens is None and isinstance(step.get("usage"), dict):
        usage = step["usage"]
        for key in ("prompt_tokens", "input_tokens", "tokens_in"):
            if key in usage:
                input_tokens = usage[key]
                break

    if input_tokens is None:
        input_tokens = 0

    # Output token aliases at top level
    output_tokens = None
    for key in ("output_tokens", "completion_tokens", "tokens_out", "output"):
        if key in step:
            output_tokens = step[key]
            break

    # Fallback: look inside a nested 'usage' dict
    if output_tokens is None and isinstance(step.get("usage"), dict):
        usage = step["usage"]
        for key in ("completion_tokens", "output_tokens", "tokens_out"):
            if key in usage:
                output_tokens = usage[key]
                break

    if output_tokens is None:
        output_tokens = 0

    return (str(model_id), int(input_tokens), int(output_tokens))


def _get_step_value(step, key, default=None):
    """Read `key` from a step that may be a dict or an object (e.g. SimpleNamespace)."""
    if isinstance(step, dict):
        return step.get(key, default)
    return getattr(step, key, default)


def extract_step_usage(step) -> tuple:
    """Extract (model_name, input_tokens, output_tokens) from a trajectory step.

    Tolerates either attribute-style or dict-style step records, plus common
    key aliases for input/output token counts and a nested 'usage' dict
    (e.g. as produced by OpenAI-style APIs).
    """
    # Model ID aliases
    model_id = ""
    for key in ("model_id", "model", "id", "name"):
        val = _get_step_value(step, key)
        if val is not None:
            model_id = val
            break

    # Input token aliases at top level
    input_tokens = None
    for key in ("input_tokens", "prompt_tokens", "tokens_in", "input"):
        val = _get_step_value(step, key)
        if val is not None:
            input_tokens = val
            break

    # Fallback: look inside a nested 'usage' dict
    if input_tokens is None:
        usage = _get_step_value(step, "usage")
        if isinstance(usage, dict):
            for key in ("prompt_tokens", "input_tokens", "tokens_in"):
                if key in usage and usage[key] is not None:
                    input_tokens = usage[key]
                    break

    if input_tokens is None:
        input_tokens = 0

    # Output token aliases at top level
    output_tokens = None
    for key in ("output_tokens", "completion_tokens", "tokens_out", "output"):
        val = _get_step_value(step, key)
        if val is not None:
            output_tokens = val
            break

    # Fallback: look inside a nested 'usage' dict
    if output_tokens is None:
        usage = _get_step_value(step, "usage")
        if isinstance(usage, dict):
            for key in ("completion_tokens", "output_tokens", "tokens_out"):
                if key in usage and usage[key] is not None:
                    output_tokens = usage[key]
                    break

    if output_tokens is None:
        output_tokens = 0

    return (str(model_id), int(input_tokens), int(output_tokens))


def extract_model_usage(step: dict) -> tuple[str, int, int]:
    """Extract (model, input_tokens, output_tokens) from a step dict.

    Falls back to nested 'usage' fields and zero defaults.
    """
    model = step.get('model', '')

    input_tokens = step.get('input_tokens')
    if input_tokens is None and isinstance(step.get('usage'), dict):
        input_tokens = step['usage'].get('input_tokens')
    if input_tokens is None:
        input_tokens = 0

    output_tokens = step.get('output_tokens')
    if output_tokens is None and isinstance(step.get('usage'), dict):
        output_tokens = step['usage'].get('output_tokens')
    if output_tokens is None:
        output_tokens = 0

    return (str(model), int(input_tokens), int(output_tokens))


from types import SimpleNamespace
assert extract_step_usage(SimpleNamespace(model='gpt-4o', input_tokens=1000, output_tokens=500)) == ('gpt-4o', 1000, 500)
assert extract_step_usage({'model': 'gpt-4o-mini', 'prompt_tokens': 200, 'completion_tokens': 100}) == ('gpt-4o-mini', 200, 100)

assert extract_model_usage({'model': 'gpt-4', 'input_tokens': 100, 'output_tokens': 50}) == ('gpt-4', 100, 50)
assert extract_model_usage({'model': 'gpt-4'}) == ('gpt-4', 0, 0)
assert extract_model_usage({'model': 'x', 'usage': {'input_tokens': 5, 'output_tokens': 3}}) == ('x', 5, 3)
