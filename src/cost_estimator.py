from typing import Tuple

# Pricing data: model name -> (input_usd_per_1k_tokens, output_usd_per_1k_tokens)
MODEL_PRICING = {
    'gpt-4': (0.03, 0.06),
    'gpt-4-turbo': (0.01, 0.03),
    'gpt-4o': (0.005, 0.015),
    'gpt-3.5-turbo': (0.0005, 0.0015),
    'gpt-3.5-turbo-16k': (0.003, 0.004),
}

# Conservative default pricing for unknown models
DEFAULT_PRICING = (0.001, 0.002)


def get_model_pricing(model: str) -> Tuple[float, float]:
    """Return (input_usd_per_1k_tokens, output_usd_per_1k_tokens) for a model id.
    
    Falls back to a conservative default for unknown models.
    """
    return MODEL_PRICING.get(model, DEFAULT_PRICING)
