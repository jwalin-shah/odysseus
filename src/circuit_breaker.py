import time


class CircuitBreaker:
    def __init__(self, fail_threshold, reset_timeout, time_func=time.monotonic):
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self._time_func = time_func
        self._failures = 0
        self._opened_at = None
        self._state = 'closed'

    @property
    def state(self):
        return self._state

    def _record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.fail_threshold:
            self._state = 'open'
            self._opened_at = self._time_func()

    def _maybe_half_open(self) -> None:
        if self._state == 'open' and (self._time_func() - self._opened_at) >= self.reset_timeout:
            self._state = 'half_open'
