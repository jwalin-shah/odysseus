from collections import defaultdict


def aggregate_by_model(trajectory_log: list[dict]) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = defaultdict(
        lambda: {'input_tokens': 0, 'output_tokens': 0}
    )
    for entry in trajectory_log:
        model = entry['model']
        result[model]['input_tokens'] += entry['input_tokens']
        result[model]['output_tokens'] += entry['output_tokens']
    return dict(result)
