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
