def get_model_pricing(model_id: str) -> tuple[float, float]:
    pricing = {
        'gpt-4o-mini': (0.00015, 0.0006),
        'gpt-4o': (0.0025, 0.01),
        'gpt-4-turbo': (0.01, 0.03),
        'gpt-4': (0.03, 0.06),
        'gpt-3.5-turbo': (0.0005, 0.0015),
        'claude-3-opus': (0.015, 0.075),
        'claude-3-sonnet': (0.003, 0.015),
        'claude-3-haiku': (0.00025, 0.00125),
    }
    return pricing.get(model_id, (0.0, 0.0))
