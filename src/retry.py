def backoff_sequence(retries: int, base: float, max_delay: float | None = None) -> list[float]:
    result = []
    for i in range(retries):
        delay = base * (2 ** i)
        if max_delay is not None:
            delay = min(delay, max_delay)
        result.append(delay)
    return result


def _attempts_log(attempts: list) -> str:
    if not attempts:
        return 'no attempts'
    parts = []
    for a in attempts:
        status = 'pass' if a.get('passed') else 'fail'
        parts.append(f"t={a.get('temp')}/s={a.get('score')}/{status}")
    return f"attempts[{' ; '.join(parts)}]"


if __name__ == '__main__':
    log = _attempts_log([{'temp': 0.1, 'score': 0.0, 'passed': False}, {'temp': 0.5, 'score': 1.0, 'passed': True}])
    assert 't=0.1' in log and 'fail' in log and 't=0.5' in log and 'pass' in log
    assert _attempts_log([]) == 'no attempts'
