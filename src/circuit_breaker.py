import time


class CircuitBreaker:
    def __init__(self, fail_threshold: int, cooldown: float) -> None:
        self.fail_threshold = fail_threshold
        self.cooldown = cooldown
        self._time_func = time.monotonic
        self.fail_count = 0
        self._opened_at = None
        self._state = 'closed'

    @property
    def state(self):
        return self._state

    def _record_failure(self) -> None:
        self.fail_count += 1
        if self.fail_count >= self.fail_threshold:
            self._state = 'open'
            self._opened_at = self._time_func()

    def _maybe_half_open(self) -> None:
        if self._state == 'open' and (self._time_func() - self._opened_at) >= self.cooldown:
            self._state = 'half_open'
