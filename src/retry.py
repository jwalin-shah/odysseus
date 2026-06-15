def backoff_sequence(retries: int, base: float, max_delay: float | None = None) -> list[float]:
    result = []
    for i in range(retries):
        delay = base * (2 ** i)
        if max_delay is not None:
            delay = min(delay, max_delay)
        result.append(delay)
    return result
