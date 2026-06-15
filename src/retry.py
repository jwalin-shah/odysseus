def backoff_sequence(retries: int, base: float, max_delay: float | None = None) -> list[float]:
    result = []
    for i in range(retries):
        delay = base * (2 ** i)
        if max_delay is not None:
            delay = min(delay, max_delay)
        result.append(delay)
    return result


def _first_passing(attempts: list) -> dict:
    for attempt in attempts:
        if attempt.get('passed') is True:
            return attempt
    return None


assert _first_passing([{'passed': False}, {'passed': True}, {'passed': True}])['passed'] is True
assert _first_passing([{'passed': False}, {'passed': False}]) is None
assert _first_passing([]) is None
