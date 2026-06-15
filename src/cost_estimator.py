from typing import Tuple


def get_model_pricing(model_id: str) -> Tuple[float, float]:
    """Return (input_price_per_million, output_price_per_million) USD for the given model."""
    pricing_table = {
        "gpt-4o-mini": (0.15, 0.60),
        "gpt-4o": (2.50, 10.00),
        "gpt-4-turbo": (10.00, 30.00),
        "gpt-4": (30.00, 60.00),
        "gpt-3.5-turbo": (0.50, 1.50),
    }
    if model_id not in pricing_table:
        raise ValueError(f"Unknown model_id: {model_id}")
    return pricing_table[model_id]


def compute_step_cost(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Return USD cost for one trajectory step given a model and its input/output token counts."""
    input_price_per_million, output_price_per_million = get_model_pricing(model_id)
    input_cost = (input_tokens / 1_000_000.0) * input_price_per_million
    output_cost = (output_tokens / 1_000_000.0) * output_price_per_million
    return input_cost + output_cost
