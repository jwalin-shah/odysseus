from src.cost_estimator import estimate_cost, MODEL_PRICING


def test_estimate_cost_known_log_totals() -> None:
    log = [
        {'model': 'gpt-4o-mini', 'input_tokens': 500_000, 'output_tokens': 500_000},
        {'model': 'claude-haiku', 'input_tokens': 1_000_000, 'output_tokens': 250_000},
    ]
    expected = (
        500_000 * MODEL_PRICING['gpt-4o-mini']['input_per_token']
        + 500_000 * MODEL_PRICING['gpt-4o-mini']['output_per_token']
        + 1_000_000 * MODEL_PRICING['claude-haiku']['input_per_token']
        + 250_000 * MODEL_PRICING['claude-haiku']['output_per_token']
    )
    assert abs(estimate_cost(log) - expected) < 1e-6 and estimate_cost(log) > 0
