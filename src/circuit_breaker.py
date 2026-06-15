import time


class CircuitBreaker:
    def __init__(self, fail_threshold, reset_timeout):
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._state = 'closed'
        self._opened_at = None

    @property
    def state(self):
        return self._state

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.fail_threshold:
            self._state = 'open'
            self._opened_at = time.time()

    def _record_success(self) -> None:
        self._failures = 0
        self._state = 'closed'
        self._opened_at = None
