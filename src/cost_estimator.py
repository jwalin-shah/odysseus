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


def aggregate_usage_by_model(steps: list) -> dict:
    """Sum input/output token counts across steps, grouped by model name.

    Each step is expected to expose `model`, `input_tokens`, and
    `output_tokens` attributes (e.g. a SimpleNamespace, dataclass, or any
    object with those names). Missing or None values are treated as zero.

    Returns a dict mapping model name to a (total_input_tokens,
    total_output_tokens) tuple. An empty input list yields an empty dict.
    """
    result: dict = {}
    for step in steps:
        model = getattr(step, "model", "") or ""
        raw_in = getattr(step, "input_tokens", 0)
        if raw_in is None:
            input_tokens = 0
        else:
            try:
                input_tokens = int(raw_in)
            except (TypeError, ValueError):
                input_tokens = 0
        raw_out = getattr(step, "output_tokens", 0)
        if raw_out is None:
            output_tokens = 0
        else:
            try:
                output_tokens = int(raw_out)
            except (TypeError, ValueError):
                output_tokens = 0
        if model in result:
            prev_in, prev_out = result[model]
            result[model] = (prev_in + input_tokens, prev_out + output_tokens)
        else:
            result[model] = (input_tokens, output_tokens)
    return result


if __name__ == "__main__":
    from types import SimpleNamespace
    steps = [SimpleNamespace(model='gpt-4o', input_tokens=1000, output_tokens=500), SimpleNamespace(model='gpt-4o', input_tokens=2000, output_tokens=1000), SimpleNamespace(model='claude-3-5-sonnet', input_tokens=500, output_tokens=200)]
    assert aggregate_usage_by_model(steps) == {'gpt-4o': (3000, 1500), 'claude-3-5-sonnet': (500, 200)}
    assert aggregate_usage_by_model([]) == {}
