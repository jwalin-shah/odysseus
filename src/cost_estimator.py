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


def _entry_cost(entry: dict) -> float:
    pricing = MODEL_PRICING.get(entry.get("model"))
    if not pricing:
        return 0.0
    input_tokens = max(0, int(entry.get("input_tokens", 0)))
    output_tokens = max(0, int(entry.get("output_tokens", 0)))
    return input_tokens * pricing["input_per_token"] + output_tokens * pricing["output_per_token"]


def estimate_cost(log: list[dict]) -> float:
    return sum(_entry_cost(entry) for entry in log)
