_PRICING = {
    'gpt-4o-mini': (0.00015, 0.0006),
    'claude-3-5-sonnet': (0.003, 0.015),
}


def pricing_for(model: str) -> tuple[float, float]:
    return _PRICING.get(model, (0.0, 0.0))
