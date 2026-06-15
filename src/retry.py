def backoff_sequence(retries: int, base: float, max_delay: float | None = None) -> list[float]:
    result = []
    for i in range(retries):
        delay = base * (2 ** i)
        if max_delay is not None:
            delay = min(delay, max_delay)
        result.append(delay)
    return result


def _run_attempt(gen_fn, validate_fn, temp) -> dict:
    candidate = gen_fn(temp)
    passed, score = validate_fn(candidate)
    return {
        'candidate': candidate,
        'passed': passed,
        'score': score,
        'temp': temp,
    }


def _best_merge(candidates: list) -> object:
    if not candidates:
        return None
    if all(isinstance(c, str) for c in candidates):
        return max(candidates, key=len)
    return candidates[-1]


assert _run_attempt(lambda t: f'c@{t}', lambda c: (True, 1.0), 0.5) == {'candidate': 'c@0.5', 'passed': True, 'score': 1.0, 'temp': 0.5}
rec = _run_attempt(lambda t: 'x', lambda c: (False, 0.0), 0.5)
assert rec['passed'] is False and rec['score'] == 0.0 and rec['candidate'] == 'x'


assert _best_merge(['a', 'bbb', 'cc']) == 'bbb'
assert _best_merge([{'k': 1}, {'k': 2}, {'k': 3}]) == {'k': 3}
assert _best_merge([]) is None
