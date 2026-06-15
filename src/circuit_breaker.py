import time


class CircuitBreaker:
    def __init__(self, fail_threshold: int, cooldown: float, time_func=time.monotonic) -> None:
        self.fail_threshold = fail_threshold
        self.cooldown = cooldown
        self._time_func = time_func
        self._failures = 0
        self._opened_at = None
        self._state = 'closed'

    @property
    def state(self):
        return self._state

    @property
    def failures(self):
        return self._failures

    @property
    def fail_count(self):
        return self._failures

    @property
    def opened_at(self):
        return self._opened_at

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.fail_threshold:
            self._state = 'open'
            self._opened_at = self._time_func()

    def _maybe_half_open(self) -> None:
        if self._state == 'open' and (self._time_func() - self._opened_at) >= self.cooldown:
            self._state = 'half_open'

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None
        self._state = 'closed'
