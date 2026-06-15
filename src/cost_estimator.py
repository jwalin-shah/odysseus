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


def estimate_cost(trajectory_log) -> float:
    total = 0.0
    for entry in trajectory_log:
        pricing = MODEL_PRICING.get(entry.get("model"))
        if not pricing:
            continue
        total += max(0, int(entry.get("input_tokens", 0))) * pricing["input_per_token"]
        total += max(0, int(entry.get("output_tokens", 0))) * pricing["output_per_token"]
    return total
