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


# Per-1k-token USD pricing for known models.
# Source: published list prices from OpenAI and Anthropic (USD per 1M tokens
# divided by 1000). Update when vendors change rates.
_MODEL_PRICING: dict = {
    # OpenAI
    "gpt-4o": {"input_per_1k": 0.0025, "output_per_1k": 0.01},
    "gpt-4o-mini": {"input_per_1k": 0.00015, "output_per_1k": 0.0006},
    "gpt-4-turbo": {"input_per_1k": 0.01, "output_per_1k": 0.03},
    "gpt-4": {"input_per_1k": 0.03, "output_per_1k": 0.06},
    "gpt-3.5-turbo": {"input_per_1k": 0.0005, "output_per_1k": 0.0015},
    "o1": {"input_per_1k": 0.015, "output_per_1k": 0.06},
    "o1-mini": {"input_per_1k": 0.003, "output_per_1k": 0.012},
    "o3-mini": {"input_per_1k": 0.0011, "output_per_1k": 0.0044},
    # Anthropic
    "claude-3-5-sonnet": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "claude-3-5-haiku": {"input_per_1k": 0.0008, "output_per_1k": 0.004},
    "claude-3-opus": {"input_per_1k": 0.015, "output_per_1k": 0.075},
    "claude-3-sonnet": {"input_per_1k": 0.003, "output_per_1k": 0.015},
    "claude-3-haiku": {"input_per_1k": 0.00025, "output_per_1k": 0.00125},
    # DeepSeek
    "deepseek-chat": {"input_per_1k": 0.00027, "output_per_1k": 0.0011},
    "deepseek-reasoner": {"input_per_1k": 0.00055, "output_per_1k": 0.00219},
    # Google Gemini
    "gemini-1.5-pro": {"input_per_1k": 0.00125, "output_per_1k": 0.005},
    "gemini-1.5-flash": {"input_per_1k": 0.000075, "output_per_1k": 0.0003},
}

# Conservative fallback for unknown / custom / locally-served models.
# Estimating on the cheap side keeps total-cost dashboards from over-reporting.
_DEFAULT_PRICING: dict = {"input_per_1k": 0.001, "output_per_1k": 0.002}


def get_model_pricing(model_name: str) -> dict:
    """Return per-1k-token USD pricing for a model.

    Looks up ``model_name`` in the known-model table. Falls back to a
    conservative default for unknown models so downstream cost
    estimation never crashes on a new provider.

    Returns a dict with two keys: ``input_per_1k`` and ``output_per_1k``.
    """
    pricing = _MODEL_PRICING.get(model_name)
    if pricing is None:
        return {"input_per_1k": _DEFAULT_PRICING["input_per_1k"],
                "output_per_1k": _DEFAULT_PRICING["output_per_1k"]}
    return {"input_per_1k": pricing["input_per_1k"],
            "output_per_1k": pricing["output_per_1k"]}


assert get_model_pricing('gpt-4o') == {'input_per_1k': 0.0025, 'output_per_1k': 0.01}
assert get_model_pricing('claude-3-5-sonnet')['output_per_1k'] == 0.015
assert set(get_model_pricing('unknown-model-xyz').keys()) == {'input_per_1k', 'output_per_1k'}
