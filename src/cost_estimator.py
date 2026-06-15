PRICING = {
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-2024-08-06": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-mini-2024-07-18": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gpt-4-turbo": {"input": 10.00 / 1_000_000, "output": 30.00 / 1_000_000},
    "gpt-4": {"input": 30.00 / 1_000_000, "output": 60.00 / 1_000_000},
    "gpt-3.5-turbo": {"input": 0.50 / 1_000_000, "output": 1.50 / 1_000_000},
    "claude-3-5-sonnet-20241022": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-3-opus-20240229": {"input": 15.00 / 1_000_000, "output": 75.00 / 1_000_000},
    "claude-3-haiku-20240307": {"input": 0.25 / 1_000_000, "output": 1.25 / 1_000_000},
}


def entry_cost(entry: dict) -> float:
    model = entry.get("model", "")
    rates = PRICING.get(model)
    if rates is None:
        raise ValueError(f"Unknown model for cost estimation: {model!r}")
    input_tokens = entry.get("input_tokens", 0) or 0
    output_tokens = entry.get("output_tokens", 0) or 0
    return float(input_tokens) * rates["input"] + float(output_tokens) * rates["output"]


def estimate_cost(trajectory_log: list[dict]) -> float:
    if not trajectory_log:
        return 0.0
    total = 0.0
    for entry in trajectory_log:
        total += entry_cost(entry)
    return total
