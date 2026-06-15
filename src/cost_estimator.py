"""Deterministic token-cost estimation for recorded model calls."""

MODEL_PRICING = {
    "gpt-4o-mini": {
        "input_per_token": 0.15 / 1_000_000,
        "output_per_token": 0.60 / 1_000_000,
    },
    "claude-haiku": {
        "input_per_token": 0.25 / 1_000_000,
        "output_per_token": 1.25 / 1_000_000,
    },
}


def estimate_cost(log: list[dict]) -> float:
    total = 0.0
    for entry in log:
        pricing = MODEL_PRICING.get(entry.get("model"))
        if not pricing:
            continue
        total += max(0, int(entry.get("input_tokens", 0))) * pricing["input_per_token"]
        total += max(0, int(entry.get("output_tokens", 0))) * pricing["output_per_token"]
    return total


def cost_breakdown(trajectory_log) -> dict:
    """Aggregate token usage and cost per model from a trajectory log.

    Returns a dict mapping each model name to a dict with keys:
        - 'input_tokens': int   (sum of input tokens across entries)
        - 'output_tokens': int  (sum of output tokens across entries)
        - 'cost_usd': float     (sum of USD cost using MODEL_PRICING)
    """
    breakdown: dict = {}
    for entry in trajectory_log:
        model = entry.get("model")
        if not model:
            continue
        bucket = breakdown.get(model)
        if bucket is None:
            bucket = {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0}
            breakdown[model] = bucket

        input_tokens = max(0, int(entry.get("input_tokens", 0)))
        output_tokens = max(0, int(entry.get("output_tokens", 0)))

        bucket["input_tokens"] += input_tokens
        bucket["output_tokens"] += output_tokens

        pricing = MODEL_PRICING.get(model)
        if pricing is not None:
            bucket["cost_usd"] += input_tokens * pricing["input_per_token"]
            bucket["cost_usd"] += output_tokens * pricing["output_per_token"]
    return breakdown
