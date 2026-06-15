class CircuitBreaker:
    def __init__(self, fail_threshold, reset_timeout):
        self.fail_threshold = fail_threshold
        self.reset_timeout = reset_timeout
        self.failure_count = 0
        self._state = 'closed'

    @property
    def state(self) -> str:
        return self._state

    def record_failure(self) -> None:
        self.failure_count += 1
        if self.failure_count >= self.fail_threshold:
            self._state = 'open'
