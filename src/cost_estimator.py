"""Cost estimator for trajectory log entries."""

# Pricing per 1M tokens in USD
MODEL_PRICING = {
    'gpt-4o-mini': {
        'input_per_token': 0.15,
        'output_per_token': 0.60,
    },
    'gpt-4o': {
        'input_per_token': 5.00,
        'output_per_token': 15.00,
    },
    'gpt-4-turbo': {
        'input_per_token': 10.00,
        'output_per_token': 30.00,
    },
    'gpt-3.5-turbo': {
        'input_per_token': 0.50,
        'output_per_token': 1.50,
    },
}


def entry_cost(entry: dict) -> float:
    """Compute the USD cost of a single trajectory log entry.

    Args:
        entry: Dictionary containing 'model', 'input_tokens', and 'output_tokens'.

    Returns:
        Cost in USD.
    """
    model = entry.get('model')
    input_tokens = entry.get('input_tokens', 0) or 0
    output_tokens = entry.get('output_tokens', 0) or 0

    pricing = MODEL_PRICING.get(model, {'input_per_token': 0.0, 'output_per_token': 0.0})

    cost = (input_tokens / 1_000_000) * pricing['input_per_token'] + \
           (output_tokens / 1_000_000) * pricing['output_per_token']

    return float(cost)
