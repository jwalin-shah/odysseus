import time


class CircuitBreaker:
    def __init__(self, fail_threshold, reset_timeout):
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self._failures = 0
        self._opened_at = None
        self.state = 'closed'

    def _record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.fail_threshold:
            self.state = 'open'
            self._opened_at = time.monotonic()
