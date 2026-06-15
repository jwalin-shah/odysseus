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


# Per-1M-token USD pricing for known models: (input_price, output_price).
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o1-preview": (15.00, 60.00),
    # Anthropic
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-opus": (15.00, 75.00),
    "claude-3-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-opus-4": (15.00, 75.00),
    "claude-haiku-4": (0.80, 4.00),
    # DeepSeek
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
    # Google
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
}


def get_model_pricing(model: str) -> tuple[float, float]:
    """Return (input_price_per_1m, output_price_per_1m) in USD for ``model``.

    Unknown models return ``(0.0, 0.0)`` so downstream cost calculation
    degrades to zero rather than raising.
    """
    return _MODEL_PRICING.get(model, (0.0, 0.0))


def calculate_model_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute the USD cost for the given token counts of a single model.

    Uses :func:`get_model_pricing` for per-1M-token rates and rounds the
    result to 6 decimal places.
    """
    input_price, output_price = get_model_pricing(model)
    cost = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
    return round(cost, 6)


if __name__ == "__main__":
    assert calculate_model_cost('gpt-4o', 1000, 500) == 0.0075
    assert calculate_model_cost('claude-3-5-sonnet', 500, 200) == 0.0045
    assert calculate_model_cost('gpt-4o', 0, 0) == 0.0
