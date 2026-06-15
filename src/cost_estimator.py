from typing import Dict, Tuple


def model_pricing_table() -> Dict[str, Tuple[float, float]]:
    """Returns a static table mapping model name -> (USD per 1K input tokens, USD per 1K output tokens) used by all cost computations."""
    return {
        'gpt-4o-mini': (0.00015, 0.0006),
        'gpt-4o': (0.0025, 0.01),
        'gpt-4-turbo': (0.01, 0.03),
        'gpt-3.5-turbo': (0.0005, 0.0015),
        'claude-3-5-sonnet': (0.003, 0.015),
        'claude-3-opus': (0.015, 0.075),
        'claude-3-haiku': (0.00025, 0.00125),
    }
